"""
Schemas compatibles con Apple HealthKit.

Cuando en la Fase 2 se sustituya este simulador por la app iOS real,
los mensajes que la app exporte vendrán con exactamente la misma estructura
(es la que devuelve HKHealthStore al consultar las samples).

Referencia oficial:
  https://developer.apple.com/documentation/healthkit/data_types
"""

from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Optional


# --------------------------------------------------------------------------- #
# Identificadores de tipo (subset de los que usaremos)
# --------------------------------------------------------------------------- #
class HKType:
    HEART_RATE         = "HKQuantityTypeIdentifierHeartRate"
    RESTING_HR         = "HKQuantityTypeIdentifierRestingHeartRate"
    HRV_SDNN           = "HKQuantityTypeIdentifierHeartRateVariabilitySDNN"
    OXYGEN_SATURATION  = "HKQuantityTypeIdentifierOxygenSaturation"
    BODY_TEMPERATURE   = "HKQuantityTypeIdentifierBodyTemperature"
    ACTIVE_ENERGY      = "HKQuantityTypeIdentifierActiveEnergyBurned"
    STEP_COUNT         = "HKQuantityTypeIdentifierStepCount"
    SLEEP_ANALYSIS     = "HKCategoryTypeIdentifierSleepAnalysis"
    RESPIRATORY_RATE   = "HKQuantityTypeIdentifierRespiratoryRate"


class HKUnit:
    BPM        = "count/min"
    MS         = "ms"
    PERCENT    = "%"
    CELSIUS    = "degC"
    KCAL       = "kcal"
    COUNT      = "count"
    BREATHS_PM = "count/min"


class HKSleepStage:
    AWAKE          = "HKCategoryValueSleepAnalysisAwake"
    IN_BED         = "HKCategoryValueSleepAnalysisInBed"
    ASLEEP_CORE    = "HKCategoryValueSleepAnalysisAsleepCore"      # N1+N2 ligero
    ASLEEP_DEEP    = "HKCategoryValueSleepAnalysisAsleepDeep"      # N3 profundo
    ASLEEP_REM     = "HKCategoryValueSleepAnalysisAsleepREM"
    ASLEEP_UNSPEC  = "HKCategoryValueSleepAnalysisAsleepUnspecified"


# --------------------------------------------------------------------------- #
# Sample tipada
# --------------------------------------------------------------------------- #
@dataclass
class HKSample:
    """Estructura equivalente a HKQuantitySample / HKCategorySample."""
    user_id: int
    type: str
    unit: str
    value: float
    start_date: str
    end_date: str
    source_name: str = "SueñoIA Wearable Simulator"
    source_version: str = "1.0.0"
    device: str = "Apple Watch Series 9 (simulado)"
    metadata: Optional[dict] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        if d["metadata"] is None:
            d.pop("metadata")
        return d


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def iso_now() -> str:
    """ISO 8601 con timezone, formato Apple."""
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def make_sample(
    user_id: int,
    type_: str,
    unit: str,
    value: float,
    start_date: str = None,
    end_date: str = None,
    metadata: dict = None,
) -> HKSample:
    """Crea una HKSample con timestamps automáticos si no se pasan."""
    now = iso_now()
    return HKSample(
        user_id=user_id,
        type=type_,
        unit=unit,
        value=value,
        start_date=start_date or now,
        end_date=end_date or now,
        metadata=metadata,
    )
