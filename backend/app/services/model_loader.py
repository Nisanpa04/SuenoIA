"""Carga el modelo de calidad del sueño desde el MLflow Registry."""
from __future__ import annotations

import logging
from typing import Optional

import mlflow
import mlflow.sklearn

log = logging.getLogger("model")

MLFLOW_URI       = "http://localhost:5500"
REGISTERED_NAME  = "suenoia-sleep"

_model = None


def get_model():
    """Carga (perezosamente) la última versión del modelo registrada."""
    global _model
    if _model is None:
        mlflow.set_tracking_uri(MLFLOW_URI)
        try:
            uri = f"models:/{REGISTERED_NAME}/latest"
            _model = mlflow.sklearn.load_model(uri)
            log.info(f"✅ Modelo cargado: {uri}")
        except Exception as e:
            log.warning(f"No se pudo cargar el modelo desde MLflow: {e}")
            raise
    return _model


def reload_model():
    """Fuerza recarga del modelo (útil tras un nuevo entrenamiento)."""
    global _model
    _model = None
    return get_model()


def quality_to_category(q: float) -> str:
    if q <= 6: return "Insuficiente"
    if q <= 8: return "Buena"
    return "Excelente"


def quality_to_score_100(q: float) -> float:
    q = max(1.0, min(10.0, float(q)))
    return round(q * 10, 1)
