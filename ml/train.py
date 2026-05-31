#!/usr/bin/env python3
"""
SueñoIA — Entrenamiento dual con MLflow tracking.

Entrena DOS modelos sobre el mismo dataset:
  1) PySpark MLlib GBTRegressor  (tooling distribuido)
  2) scikit-learn GradientBoostingRegressor  (baseline + producción)

Registra ambos en MLflow (http://localhost:5500) y promociona el sklearn al
registry "suenoia-sleep" como modelo de producción (el backend lo cargará
desde ahí).

Uso:
    python train.py
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# Compatibilidad Java 17+ con Spark 3.5 (mismo trick que el streaming)
# --------------------------------------------------------------------------- #
import os

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

os.environ["JDK_JAVA_OPTIONS"] = _JAVA17_OPTS
os.environ["PYSPARK_SUBMIT_ARGS"] = (
    f'--driver-java-options "{_JAVA17_OPTS}" '
    f'--conf spark.driver.extraJavaOptions="{_JAVA17_OPTS}" '
    f'--conf spark.executor.extraJavaOptions="{_JAVA17_OPTS}" '
    f'pyspark-shell'
)

# --------------------------------------------------------------------------- #
import logging
import time
from pathlib import Path

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from data_loader import CATEGORICAL_FEATURES, NUMERIC_FEATURES, TARGET, load_clean_pandas


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("train")


# --------------------------------------------------------------------------- #
MLFLOW_URI = "http://localhost:5500"
# v2: experiment nuevo tras pasar a serve-artifacts (el viejo guardaba la ruta /mlflow rota)
EXPERIMENT_NAME = "suenoia-sleep-quality-v2"
REGISTERED_NAME = "suenoia-sleep"
RANDOM_SEED = 42


# --------------------------------------------------------------------------- #
# 1) Entrenamiento con scikit-learn (rápido + portable, va al registry)
# --------------------------------------------------------------------------- #
def train_sklearn(df: pd.DataFrame) -> dict:
    X = df[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    y = df[TARGET]

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_SEED,
    )

    preprocessor = ColumnTransformer([
        ("num", StandardScaler(), NUMERIC_FEATURES),
        ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
    ])
    pipe = Pipeline([
        ("prep", preprocessor),
        ("model", GradientBoostingRegressor(
            n_estimators=200, learning_rate=0.1,
            max_depth=3, random_state=RANDOM_SEED,
        )),
    ])

    t0 = time.time()
    pipe.fit(X_tr, y_tr)
    train_secs = time.time() - t0

    preds = pipe.predict(X_te)
    metrics = {
        "test_mae":  mean_absolute_error(y_te, preds),
        "test_rmse": mean_squared_error(y_te, preds, squared=False),
        "test_r2":   r2_score(y_te, preds),
        "train_time_secs": train_secs,
        "n_train": len(X_tr),
        "n_test":  len(X_te),
    }

    log.info("  sklearn → MAE=%.3f  RMSE=%.3f  R²=%.3f  (%.1fs)",
             metrics["test_mae"], metrics["test_rmse"], metrics["test_r2"], train_secs)

    # Log a MLflow
    with mlflow.start_run(run_name="sklearn-gbr") as run:
        mlflow.log_param("framework", "sklearn")
        mlflow.log_param("model", "GradientBoostingRegressor")
        mlflow.log_param("n_estimators", 200)
        mlflow.log_param("learning_rate", 0.1)
        mlflow.log_param("max_depth", 3)
        mlflow.log_metrics({k: v for k, v in metrics.items() if isinstance(v, (int, float))})

        # Modelo + ejemplo de input para la firma
        input_example = X_tr.head(2)
        mlflow.sklearn.log_model(
            sk_model=pipe,
            artifact_path="model",
            registered_model_name=REGISTERED_NAME,
            input_example=input_example,
        )
        log.info("  sklearn registrado en MLflow registry como '%s'", REGISTERED_NAME)
        metrics["mlflow_run_id"] = run.info.run_id

    return metrics


# --------------------------------------------------------------------------- #
# 2) Entrenamiento con PySpark MLlib (Big Data tooling)
# --------------------------------------------------------------------------- #
def train_pyspark(pdf: pd.DataFrame) -> dict:
    from pyspark.sql import SparkSession
    from pyspark.ml import Pipeline as SparkPipeline
    from pyspark.ml.evaluation import RegressionEvaluator
    from pyspark.ml.feature import OneHotEncoder as SOneHotEncoder
    from pyspark.ml.feature import StandardScaler as SStandardScaler
    from pyspark.ml.feature import StringIndexer, VectorAssembler
    from pyspark.ml.regression import GBTRegressor

    spark = (
        SparkSession.builder
        .appName("suenoia-mllib-train")
        .master("local[*]")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.driver.memory", "1g")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")

    sdf = spark.createDataFrame(pdf)
    train_sdf, test_sdf = sdf.randomSplit([0.8, 0.2], seed=RANDOM_SEED)

    # Pipeline: indexers + onehot + scaler + vectorassembler + GBT
    indexers = [
        StringIndexer(inputCol=c, outputCol=f"{c}_idx", handleInvalid="keep")
        for c in CATEGORICAL_FEATURES
    ]
    encoders = [
        SOneHotEncoder(inputCols=[f"{c}_idx"], outputCols=[f"{c}_oh"])
        for c in CATEGORICAL_FEATURES
    ]
    num_assembler = VectorAssembler(
        inputCols=NUMERIC_FEATURES, outputCol="num_raw",
    )
    scaler = SStandardScaler(
        inputCol="num_raw", outputCol="num_scaled",
        withMean=True, withStd=True,
    )
    full_assembler = VectorAssembler(
        inputCols=[f"{c}_oh" for c in CATEGORICAL_FEATURES] + ["num_scaled"],
        outputCol="features",
    )
    gbt = GBTRegressor(
        labelCol=TARGET, featuresCol="features",
        maxIter=200, maxDepth=3, stepSize=0.1, seed=RANDOM_SEED,
    )

    pipeline = SparkPipeline(stages=[
        *indexers, *encoders, num_assembler, scaler, full_assembler, gbt,
    ])

    t0 = time.time()
    fitted = pipeline.fit(train_sdf)
    train_secs = time.time() - t0

    preds = fitted.transform(test_sdf)
    evaluator = RegressionEvaluator(labelCol=TARGET, predictionCol="prediction")
    mae  = evaluator.evaluate(preds, {evaluator.metricName: "mae"})
    rmse = evaluator.evaluate(preds, {evaluator.metricName: "rmse"})
    r2   = evaluator.evaluate(preds, {evaluator.metricName: "r2"})

    metrics = {
        "test_mae": mae, "test_rmse": rmse, "test_r2": r2,
        "train_time_secs": train_secs,
        "n_train": train_sdf.count(), "n_test": test_sdf.count(),
    }
    log.info("  pyspark → MAE=%.3f  RMSE=%.3f  R²=%.3f  (%.1fs)",
             mae, rmse, r2, train_secs)

    with mlflow.start_run(run_name="pyspark-gbt") as run:
        mlflow.log_param("framework", "pyspark-mllib")
        mlflow.log_param("model", "GBTRegressor")
        mlflow.log_param("maxIter", 200)
        mlflow.log_param("maxDepth", 3)
        mlflow.log_param("stepSize", 0.1)
        mlflow.log_metrics({k: v for k, v in metrics.items() if isinstance(v, (int, float))})
        # No registramos en el registry (el backend usará el sklearn por velocidad)
        metrics["mlflow_run_id"] = run.info.run_id

    spark.stop()
    return metrics


# --------------------------------------------------------------------------- #
def main():
    log.info("📂 Cargando dataset…")
    df = load_clean_pandas()
    log.info(f"  {len(df)} filas, {df.shape[1]} columnas")

    log.info("🔌 Conectando a MLflow %s", MLFLOW_URI)
    mlflow.set_tracking_uri(MLFLOW_URI)
    mlflow.set_experiment(EXPERIMENT_NAME)

    log.info("🧠 Entrenando scikit-learn…")
    sk = train_sklearn(df)

    log.info("⚙️  Entrenando PySpark MLlib (puede tardar 30-60s la primera vez)…")
    sp = train_pyspark(df)

    # ---- Resumen comparativo ----
    log.info("\n📊 RESUMEN COMPARATIVO:")
    log.info(f"  {'modelo':<20} {'MAE':>8} {'RMSE':>8} {'R²':>8} {'segs':>8}")
    log.info(f"  {'sklearn GBR':<20} {sk['test_mae']:>8.3f} {sk['test_rmse']:>8.3f} "
             f"{sk['test_r2']:>8.3f} {sk['train_time_secs']:>8.1f}")
    log.info(f"  {'PySpark MLlib GBT':<20} {sp['test_mae']:>8.3f} {sp['test_rmse']:>8.3f} "
             f"{sp['test_r2']:>8.3f} {sp['train_time_secs']:>8.1f}")

    log.info("\n✅ Entrenamiento finalizado")
    log.info(f"   sklearn  run: {sk['mlflow_run_id']}")
    log.info(f"   pyspark  run: {sp['mlflow_run_id']}")
    log.info(f"\n   Visualiza experimentos en {MLFLOW_URI}")
    log.info(f"   El modelo sklearn está registrado como '{REGISTERED_NAME}' (Production)")


if __name__ == "__main__":
    main()
