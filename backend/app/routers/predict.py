"""Endpoint /predict — predicción de calidad de sueño con el modelo del registry."""
from __future__ import annotations

import logging
from typing import Literal, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.model_loader import (
    get_model, quality_to_category, quality_to_score_100, reload_model,
)

log = logging.getLogger("router.predict")
router = APIRouter(prefix="/predict", tags=["ml"])


# ----------------- schemas -----------------
class PredictRequest(BaseModel):
    age: int = Field(..., ge=10, le=100)
    gender: Literal["Male", "Female"]
    sleep_duration: float = Field(..., ge=1, le=14)
    physical_activity: int = Field(..., ge=0, le=300)
    stress_level: int = Field(..., ge=1, le=10)
    bmi_category: Literal["Normal", "Overweight", "Obese"]
    heart_rate: int = Field(..., ge=40, le=200)
    systolic: int = Field(..., ge=80, le=200)
    sleep_disorder: Literal["None", "Insomnia", "Sleep Apnea"] = "None"


class PredictResponse(BaseModel):
    raw_value: float
    score_100: float
    category: str
    model_version: Optional[str] = None


# Mapeo snake_case (API) ↔ columnas del dataset
_API_TO_MODEL = {
    "age":               "Age",
    "sleep_duration":    "Sleep Duration",
    "physical_activity": "Physical Activity Level",
    "stress_level":      "Stress Level",
    "heart_rate":        "Heart Rate",
    "systolic":          "Systolic",
    "gender":            "Gender",
    "bmi_category":      "BMI Category",
    "sleep_disorder":    "Sleep Disorder",
}


@router.post("", response_model=PredictResponse)
def predict(req: PredictRequest) -> PredictResponse:
    try:
        model = get_model()
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Modelo no disponible ({e}). "
                "Ejecuta primero `python ml/train.py` para entrenar y registrar."
            ),
        )

    # Construye DataFrame con las columnas que espera el pipeline
    api_payload = req.model_dump()
    model_input = {model_col: api_payload[api_key]
                   for api_key, model_col in _API_TO_MODEL.items()}
    X = pd.DataFrame([model_input])

    raw = float(model.predict(X)[0])
    return PredictResponse(
        raw_value=round(raw, 3),
        score_100=quality_to_score_100(raw),
        category=quality_to_category(raw),
    )


@router.post("/reload")
def reload():
    """Fuerza al backend a recargar el modelo (tras un nuevo entrenamiento)."""
    try:
        reload_model()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
    return {"status": "reloaded"}
