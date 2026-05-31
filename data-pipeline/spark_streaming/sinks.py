"""
Sinks: escritura desde los foreachBatch a Elasticsearch, TimescaleDB y Kafka.

Cada sink mantiene su propia conexión (perezosa). En PySpark Streaming, los
foreachBatch corren en el driver, así que es seguro mantener clientes en
variables globales del módulo.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

from elasticsearch import Elasticsearch, helpers
from kafka import KafkaProducer
import psycopg2
import psycopg2.extras


log = logging.getLogger("sinks")

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
ES_HOST  = "http://localhost:19200"
PG_DSN   = "host=localhost port=5433 dbname=suenoia user=suenoia password=suenoia_pass"
KAFKA_BOOTSTRAP = "localhost:19092"
KAFKA_ALERTS_TOPIC = "alerts.detected"


# --------------------------------------------------------------------------- #
# Clientes perezosos
# --------------------------------------------------------------------------- #
_es: Optional[Elasticsearch] = None
_pg = None
_producer: Optional[KafkaProducer] = None


def _get_es() -> Elasticsearch:
    global _es
    if _es is None:
        _es = Elasticsearch(ES_HOST, request_timeout=10)
    return _es


def _get_pg():
    global _pg
    if _pg is None or _pg.closed:
        _pg = psycopg2.connect(PG_DSN)
        _pg.autocommit = True
    return _pg


def _get_kafka() -> KafkaProducer:
    global _producer
    if _producer is None:
        _producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            linger_ms=20,
            compression_type="gzip",
        )
    return _producer


# --------------------------------------------------------------------------- #
# Elasticsearch
# --------------------------------------------------------------------------- #
def es_write_raw(rows: list[dict]):
    if not rows:
        return
    today = datetime.utcnow().strftime("%Y-%m-%d")
    actions = [
        {
            "_index": f"biometrics-{today}",
            "_source": {
                "@timestamp": r.get("start_date"),
                "user_id": r["user_id"],
                "metric":  r.get("metric"),
                "value":   r.get("value"),
                "unit":    r.get("unit"),
                "phase":   (r.get("metadata") or {}).get("phase"),
                "source":  r.get("source_name", "simulator"),
                "ingested_at": r.get("ingested_at"),
            },
        }
        for r in rows
    ]
    try:
        helpers.bulk(_get_es(), actions, request_timeout=10)
    except Exception as e:
        log.warning(f"[ES raw] write failed: {e}")


def es_write_agg(rows: list[dict]):
    if not rows:
        return
    today = datetime.utcnow().strftime("%Y-%m-%d")
    actions = [
        {
            "_index": f"biometrics-agg-{today}",
            "_source": {
                "@timestamp": r["window_start"],
                "window_end": r["window_end"],
                "user_id":    r["user_id"],
                "metric":     r["metric"],
                "avg_value":  r["avg_value"],
                "min_value":  r["min_value"],
                "max_value":  r["max_value"],
                "n_samples":  r["n_samples"],
            },
        }
        for r in rows
    ]
    try:
        helpers.bulk(_get_es(), actions, request_timeout=10)
    except Exception as e:
        log.warning(f"[ES agg] write failed: {e}")


# --------------------------------------------------------------------------- #
# TimescaleDB
# --------------------------------------------------------------------------- #
def pg_write_biometrics(rows: list[dict]):
    if not rows:
        return
    try:
        conn = _get_pg()
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO biometrics (time, user_id, metric, value, source, metadata)
                VALUES %s
                """,
                [
                    (
                        r.get("start_date"),
                        r["user_id"],
                        r.get("metric"),
                        r.get("value"),
                        r.get("source_name", "simulator"),
                        json.dumps(r.get("metadata") or {}),
                    )
                    for r in rows
                ],
                page_size=500,
            )
    except Exception as e:
        log.warning(f"[PG biometrics] write failed: {e}")


def pg_write_alerts(alerts: list[dict]):
    if not alerts:
        return
    try:
        conn = _get_pg()
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO alerts (user_id, created_at, severity, category, title, text, metadata)
                VALUES %s
                """,
                [
                    (
                        a["user_id"],
                        a["created_at"],
                        a["severity"],
                        a["category"],
                        a["title"],
                        a["text"],
                        json.dumps({
                            k: v for k, v in a.items()
                            if k not in {"user_id", "created_at", "severity",
                                         "category", "title", "text"}
                        }),
                    )
                    for a in alerts
                ],
                page_size=200,
            )
    except Exception as e:
        log.warning(f"[PG alerts] write failed: {e}")


# --------------------------------------------------------------------------- #
# Kafka alerts (para que el backend reaccione vía WebSocket / Telegram)
# --------------------------------------------------------------------------- #
def kafka_publish_alerts(alerts: list[dict]):
    if not alerts:
        return
    producer = _get_kafka()
    for a in alerts:
        try:
            producer.send(KAFKA_ALERTS_TOPIC, value=a, key=str(a["user_id"]))
        except Exception as e:
            log.warning(f"[Kafka alerts] failed: {e}")
    producer.flush(timeout=5)
