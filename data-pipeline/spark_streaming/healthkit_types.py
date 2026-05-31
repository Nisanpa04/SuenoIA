"""
Constantes clínicas usadas por las reglas de anomalía.
Valores extraídos de literatura médica estándar (no son recomendaciones médicas).
"""

# Frecuencia cardíaca (bpm)
HR_BRADYCARDIA       = 50    # < 50 bpm en reposo = bradicardia
HR_TACHYCARDIA       = 100   # > 100 bpm en reposo = taquicardia
HR_SLEEP_MAX         = 90    # umbral durante sueño
HR_DEEP_SLEEP_MAX    = 70    # umbral durante deep sleep

# Variabilidad cardíaca SDNN (ms)
HRV_VERY_LOW         = 20    # < 20 ms estrés crónico
HRV_LOW              = 35
HRV_NORMAL           = 55
HRV_HIGH             = 80

# Saturación de oxígeno (%)
SPO2_NORMAL          = 95
SPO2_LOW             = 92    # < 92 = baja
SPO2_HYPOXIA         = 90    # < 90 = hipoxia

# Temperatura corporal (°C)
TEMP_LOW_HYPOTHERMIA = 35.5
TEMP_NORMAL_LO       = 36.1
TEMP_NORMAL_HI       = 37.2
TEMP_HIGH_FEVER      = 38.0

# Pasos
STEPS_DAILY_TARGET   = 7000

# Respiración (rpm)
RR_NORMAL_LO         = 12
RR_NORMAL_HI         = 20
