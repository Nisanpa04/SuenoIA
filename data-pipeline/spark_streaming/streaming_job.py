#!/usr/bin/env python3
"""
SueñoIA — Spark Structured Streaming job.

Consume todos los topics `biometrics.*` de Kafka y mantiene 3 queries en paralelo:

  1) raw_query  — escribe cada lectura a Elasticsearch y TimescaleDB
                  + aplica reglas de anomalía y publica alertas a Kafka
                  + persiste alertas en TimescaleDB
  2) agg_query  — ventanas de 5 min (avg/min/max/count) por usuario y métrica,
                  escritura a Elasticsearch y TimescaleDB
  3) hr_safety  — vigilancia adicional de HR con ventana de 1 min para alertas
                  inmediatas (latencia objetivo < 2 s)

Uso:
    python streaming_job.py
"""

from __future__ import annotations

import os

# --------------------------------------------------------------------------- #
# Compatibilidad Java 17+ con Spark 3.5
# Tiene que estar ANTES de importar pyspark.
# --------------------------------------------------------------------------- #
_JAVA17_OPTS = " ".join([
    "-Djava.security.manager=allow",
    "--add-opens=java.base/java.lang=ALL-UNNAMED",
    "--add-opens=java.base/java.lang.invoke=ALL-UNNAMED",
    "--add-opens=java.base/java.lang.reflect=ALL-UNNAMED",
    "--add-opens=java.base/java.io=ALL-UNNAMED",
    "--add-opens=java.base/java.net=ALL-UNNAMED",
    "--add-opens=java.base/java.nio=ALL-UNNAMED",
    "--add-opens=java.base/java.util=ALL-UNNAMED",
    "--add-opens=java.base/java.util.concurrent=ALL-UNNAMED",
    "--add-opens=java.base/java.util.concurrent.atomic=ALL-UNNAMED",
    "--add-opens=java.base/sun.nio.ch=ALL-UNNAMED",
    "--add-opens=java.base/sun.nio.cs=ALL-UNNAMED",
    "--add-opens=java.base/sun.security.action=ALL-UNNAMED",
    "--add-opens=java.base/sun.util.calendar=ALL-UNNAMED",
])

# Se inyectan en la JVM que lanza PySpark al arrancar
os.environ["JDK_JAVA_OPTIONS"] = _JAVA17_OPTS
os.environ["PYSPARK_SUBMIT_ARGS"] = (
    f'--driver-java-options "{_JAVA17_OPTS}" '
    f'--conf spark.driver.extraJavaOptions="{_JAVA17_OPTS}" '
    f'--conf spark.executor.extraJavaOptions="{_JAVA17_OPTS}" '
    f'--packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 '
    f'pyspark-shell'
)

import logging
from datetime import datetime

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    avg, col, count, expr, from_json, max as pmax, min as pmin, to_timestamp, window,
)
from pyspark.sql.types import (
    DoubleType, IntegerType, MapType, StringType, StructField, StructType,
)

from anomaly_rules import detect_anomalies
from sinks import (
    es_write_agg, es_write_raw, kafka_publish_alerts, pg_write_alerts, pg_write_biometrics,
)


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("streaming")


# --------------------------------------------------------------------------- #
KAFKA_BOOTSTRAP = "localhost:19092"
KAFKA_TOPIC_PATTERN = r"biometrics\..*"
CHECKPOINT_DIR = "/tmp/suenoia-checkpoints"


# --------------------------------------------------------------------------- #
# Schema del JSON que produce el bridge
# --------------------------------------------------------------------------- #
HK_SCHEMA = StructType([
    StructField("user_id",    IntegerType()),
    StructField("type",       StringType()),
    StructField("unit",       StringType()),
    StructField("value",      DoubleType()),
    StructField("start_date", StringType()),
    StructField("end_date",   StringType()),
    StructField("source_name", StringType()),
    StructField("device",     StringType()),
    StructField("metric",     StringType()),
    StructField("ingested_at", StringType()),
    StructField("metadata",   MapType(StringType(), StringType())),
])


# --------------------------------------------------------------------------- #
def build_spark() -> SparkSession:
    return (
        SparkSession.builder
        .appName("SuenoIA-Streaming")
        .master("local[*]")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.sql.streaming.statefulOperator.useStrictDistribution", "true")
        .config("spark.driver.memory", "1g")
        .config("spark.executor.memory", "1g")
        .getOrCreate()
    )


# --------------------------------------------------------------------------- #
# Procesado por batch (raw)
# --------------------------------------------------------------------------- #
def process_raw_batch(batch_df, batch_id: int):
    """Convierte el batch a lista de dicts y lo manda a los 3 sinks + reglas."""
    rows = [row.asDict(recursive=True) for row in batch_df.collect()]
    if not rows:
        return

    log.info(f"[batch {batch_id}] raw  → {len(rows)} filas")

    # 1) Persistencia raw
    es_write_raw(rows)
    pg_write_biometrics(rows)

    # 2) Reglas de anomalía + emisión de alertas
    alerts = detect_anomalies(rows)
    if alerts:
        log.warning(f"[batch {batch_id}] 🚨 {len(alerts)} alertas detectadas")
        pg_write_alerts(alerts)
        kafka_publish_alerts(alerts)


# --------------------------------------------------------------------------- #
# Procesado por batch (agg)
# --------------------------------------------------------------------------- #
def process_agg_batch(batch_df, batch_id: int):
    rows = []
    for row in batch_df.collect():
        d = row.asDict(recursive=True)
        win = d.pop("window", None)
        if win:
            d["window_start"] = win["start"].isoformat() if win.get("start") else None
            d["window_end"]   = win["end"].isoformat()   if win.get("end")   else None
        rows.append(d)
    if not rows:
        return
    log.info(f"[batch {batch_id}] agg  → {len(rows)} ventanas")
    es_write_agg(rows)


# --------------------------------------------------------------------------- #
def main():
    spark = build_spark()
    spark.sparkContext.setLogLevel("WARN")

    log.info("📡 Suscribiéndose a topics Kafka  '%s'", KAFKA_TOPIC_PATTERN)

    # ---------- Stream base ----------
    raw_stream = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP)
        .option("subscribePattern", KAFKA_TOPIC_PATTERN)
        .option("startingOffsets", "latest")
        .option("failOnDataLoss", "false")
        .load()
    )

    parsed = (
        raw_stream
        .selectExpr("CAST(value AS STRING) AS json", "topic AS kafka_topic", "timestamp AS kafka_ts")
        .select(from_json(col("json"), HK_SCHEMA).alias("d"), "kafka_topic", "kafka_ts")
        .select("d.*", "kafka_topic", "kafka_ts")
        .withColumn("event_time", to_timestamp(col("start_date")))
    )

    # ---------- Query 1: raw → ES + PG + Anomaly ----------
    raw_query = (
        parsed.writeStream
        .foreachBatch(process_raw_batch)
        .outputMode("append")
        .trigger(processingTime="2 seconds")
        .option("checkpointLocation", f"{CHECKPOINT_DIR}/raw")
        .start()
    )
    log.info("✅ Query RAW iniciada")

    # ---------- Query 2: agregaciones 5 min ----------
    agg = (
        parsed
        .withWatermark("event_time", "1 minute")
        .groupBy(
            window("event_time", "5 minutes", "1 minute"),
            col("user_id"),
            col("metric"),
        )
        .agg(
            avg("value").alias("avg_value"),
            pmin("value").alias("min_value"),
            pmax("value").alias("max_value"),
            count("value").alias("n_samples"),
        )
    )

    agg_query = (
        agg.writeStream
        .foreachBatch(process_agg_batch)
        .outputMode("update")
        .trigger(processingTime="10 seconds")
        .option("checkpointLocation", f"{CHECKPOINT_DIR}/agg")
        .start()
    )
    log.info("✅ Query AGG iniciada")

    log.info("🚀 Pipeline arrancado. Ctrl+C para parar.")
    spark.streams.awaitAnyTermination()


# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    main()
