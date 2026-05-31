"""
Carga el dataset Sleep Health and Lifestyle de Kaggle.
Reutilizamos el CSV ya descargado en v1 si está disponible.
"""

from __future__ import annotations

from pathlib import Path
import pandas as pd

# Búsqueda en orden: v2 local → v1
_SEARCH_PATHS = [
    Path(__file__).resolve().parent / "data" / "sleep_dataset.csv",
    Path(__file__).resolve().parent.parent.parent / "suenoia" / "backend" / "data" / "sleep_dataset.csv",
]


def find_csv() -> Path:
    for p in _SEARCH_PATHS:
        if p.exists():
            return p
    raise FileNotFoundError(
        "No se encontró sleep_dataset.csv. Copialo desde v1 a "
        "suenoia-v2/ml/data/sleep_dataset.csv o descárgalo de Kaggle."
    )


def load_clean_pandas() -> pd.DataFrame:
    """Lee y limpia el dataset (mismas transformaciones que v1)."""
    df = pd.read_csv(find_csv())

    # NaN en Sleep Disorder → 'None'
    df["Sleep Disorder"] = df["Sleep Disorder"].fillna("None")

    # Normal Weight → Normal
    df["BMI Category"] = df["BMI Category"].replace({"Normal Weight": "Normal"})

    # Blood Pressure "120/80" → Systolic + Diastolic
    bp = df["Blood Pressure"].str.split("/", expand=True)
    df["Systolic"]  = pd.to_numeric(bp[0])
    df["Diastolic"] = pd.to_numeric(bp[1])

    return df


# Columnas de features finales (mismas que v1)
NUMERIC_FEATURES = [
    "Age",
    "Sleep Duration",
    "Physical Activity Level",
    "Stress Level",
    "Heart Rate",
    "Systolic",
]

CATEGORICAL_FEATURES = [
    "Gender",
    "BMI Category",
    "Sleep Disorder",
]

TARGET = "Quality of Sleep"
