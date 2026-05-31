"""
Reglas de detección de anomalías sobre los datos biométricos.

Cada regla recibe una fila ya parseada (dict) y devuelve None o un dict
con la alerta. Diseñadas para ser puras y rápidas (se aplican en el
foreachBatch del streaming).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from healthkit_types import (
    HR_DEEP_SLEEP_MAX, HR_SLEEP_MAX, HR_TACHYCARDIA, HRV_VERY_LOW,
    SPO2_HYPOXIA, SPO2_LOW, TEMP_HIGH_FEVER, TEMP_LOW_HYPOTHERMIA,
)


def _new_alert(
    user_id: int, severity: str, category: str,
    title: str, text: str, metric: str, value, **extra,
) -> dict:
    """Estructura común de alerta."""
    return {
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "severity": severity,
        "category": category,
        "title": title,
        "text": text,
        "metric": metric,
        "value": value,
        **extra,
    }


# --------------------------------------------------------------------------- #
# Reglas individuales
# --------------------------------------------------------------------------- #
def rule_high_hr_during_sleep(row: dict) -> Optional[dict]:
    """HR elevada durante el sueño puede indicar pesadilla, fiebre o apnea."""
    if row.get("metric") != "heart_rate":
        return None
    phase = (row.get("metadata") or {}).get("phase", "")
    if "Asleep" not in phase:
        return None
    value = row.get("value", 0)
    if value > HR_SLEEP_MAX:
        return _new_alert(
            user_id=row["user_id"],
            severity="critical" if value > 110 else "warning",
            category="cardiovascular",
            title="Frecuencia cardíaca elevada durante el sueño",
            text=f"HR={value:.0f} bpm en fase {phase.split('Analysis')[-1]}. "
                 "Puede indicar pesadilla, fiebre o apnea del sueño.",
            metric="heart_rate",
            value=value,
            phase=phase,
        )
    return None


def rule_tachycardia(row: dict) -> Optional[dict]:
    """HR > 100 en reposo (despierto) = taquicardia."""
    if row.get("metric") != "heart_rate":
        return None
    phase = (row.get("metadata") or {}).get("phase", "")
    if "Awake" not in phase:
        return None
    value = row.get("value", 0)
    if value > HR_TACHYCARDIA + 20:    # margen razonable para actividad
        return _new_alert(
            user_id=row["user_id"],
            severity="warning",
            category="cardiovascular",
            title="Frecuencia cardíaca elevada",
            text=f"HR={value:.0f} bpm en reposo. Si no estás haciendo ejercicio, "
                 "considera tomarte 5 min de respiración guiada.",
            metric="heart_rate",
            value=value,
        )
    return None


def rule_low_spo2(row: dict) -> Optional[dict]:
    """SpO2 baja indica posible hipoxia o problema respiratorio."""
    if row.get("metric") != "oxygen":
        return None
    value = row.get("value", 100)
    if value < SPO2_HYPOXIA:
        return _new_alert(
            user_id=row["user_id"],
            severity="critical",
            category="respiratory",
            title="Saturación de oxígeno crítica",
            text=f"SpO2={value:.1f}%. Por debajo del 90% es hipoxia. "
                 "Consulta con un profesional si se repite.",
            metric="oxygen",
            value=value,
        )
    if value < SPO2_LOW:
        return _new_alert(
            user_id=row["user_id"],
            severity="warning",
            category="respiratory",
            title="Saturación de oxígeno baja",
            text=f"SpO2={value:.1f}%. Lo normal es ≥95%. "
                 "Si se repite, descarta apnea del sueño.",
            metric="oxygen",
            value=value,
        )
    return None


def rule_low_hrv(row: dict) -> Optional[dict]:
    """HRV muy baja indica estrés acumulado o falta de recuperación."""
    if row.get("metric") != "hrv":
        return None
    value = row.get("value", 100)
    if value < HRV_VERY_LOW:
        return _new_alert(
            user_id=row["user_id"],
            severity="warning",
            category="recovery",
            title="Variabilidad cardíaca muy baja",
            text=f"HRV={value:.0f} ms. Indica estrés acumulado o mala recuperación. "
                 "Prueba meditación 10 min y evita cafeína mañana.",
            metric="hrv",
            value=value,
        )
    return None


def rule_temperature(row: dict) -> Optional[dict]:
    """Fiebre o hipotermia."""
    if row.get("metric") != "temperature":
        return None
    value = row.get("value", 36.5)
    if value > TEMP_HIGH_FEVER:
        return _new_alert(
            user_id=row["user_id"],
            severity="critical",
            category="general",
            title="Temperatura corporal elevada (fiebre)",
            text=f"Temp={value:.1f} °C. Hidratación y reposo. "
                 "Si persiste >24h, consulta médico.",
            metric="temperature",
            value=value,
        )
    if value < TEMP_LOW_HYPOTHERMIA:
        return _new_alert(
            user_id=row["user_id"],
            severity="warning",
            category="general",
            title="Temperatura corporal baja",
            text=f"Temp={value:.1f} °C. Puede ser un error de medición. "
                 "Calienta la habitación si llevas frío.",
            metric="temperature",
            value=value,
        )
    return None


# --------------------------------------------------------------------------- #
# Ejecutor
# --------------------------------------------------------------------------- #
ALL_RULES = [
    rule_high_hr_during_sleep,
    rule_tachycardia,
    rule_low_spo2,
    rule_low_hrv,
    rule_temperature,
]


def detect_anomalies(rows: list[dict]) -> list[dict]:
    """Aplica todas las reglas a una colección de filas y devuelve las alertas."""
    alerts = []
    for row in rows:
        for rule in ALL_RULES:
            alert = rule(row)
            if alert:
                alerts.append(alert)
    return alerts
