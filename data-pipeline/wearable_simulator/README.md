# 🍎 Simulador de wearable + Bridge MQTT→Kafka

Esta carpeta contiene dos scripts Python que simulan la **capa de ingesta IoT** de SueñoIA. El día de mañana, cuando se desarrolle la app iOS (Fase 2), basta con apuntar el `HKHealthStore` al mismo broker MQTT y el resto del stack no cambia.

## Componentes

| Archivo | Rol |
|---------|-----|
| `wearable_simulator.py` | Emula un Apple Watch generando datos biométricos realistas (HR, HRV, SpO2, temperatura, movimiento, fases de sueño…) en formato HealthKit-compatible. Publica en Mosquitto MQTT |
| `mqtt_to_kafka_bridge.py` | Suscribe a Mosquitto y reenvía los mensajes a los topics de Kafka correspondientes (`biometrics.heart_rate`, `biometrics.hrv`, etc.) |
| `healthkit_schema.py` | Helpers + identificadores oficiales de HealthKit |

## Instalación

```bash
cd suenoia-v2/data-pipeline/wearable_simulator
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Arranque (en 2 terminales)

**Terminal 1 — Bridge (debe arrancar primero):**

```bash
source venv/bin/activate
python mqtt_to_kafka_bridge.py
```

Deberías ver:
```
🟢 Conectando a Kafka  localhost:19092...
✅ Kafka producer listo
✅ Conectado a MQTT localhost:1883
📡 Subscrito a 'suenoia/wearable/+'
```

**Terminal 2 — Simulador:**

```bash
source venv/bin/activate

# Tiempo real (1 dato cada 2 segundos)
python wearable_simulator.py

# O acelerado: simula una noche entera en 1 minuto
python wearable_simulator.py --speed 480 --start-hour 22

# O con un usuario concreto
python wearable_simulator.py --user-id 1 --speed 60
```

## Verificar que los datos fluyen

### 1. Mosquitto (MQTT)

Suscríbete desde el host:

```bash
docker exec -it suenoia-mosquitto mosquitto_sub -t 'suenoia/wearable/+' -v
```

Verás mensajes JSON cada 2 segundos.

### 2. Kafka

Abre Kafka UI: http://localhost:18080
→ Topics → `biometrics.heart_rate` → Messages

Deberías ver los mensajes llegando con `metric`, `value`, `user_id`, `ingested_at`.

### 3. Node-RED

Abre http://localhost:11880
→ deploy el flujo "MQTT Monitor"
→ panel lateral derecho (debug) verás los datos en tiempo real.

## Topics generados

| Topic MQTT | Topic Kafka | Métrica |
|------------|-------------|---------|
| `suenoia/wearable/heart_rate` | `biometrics.heart_rate` | HR (bpm) |
| `suenoia/wearable/hrv` | `biometrics.hrv` | HRV SDNN (ms) |
| `suenoia/wearable/oxygen` | `biometrics.oxygen` | SpO2 (%) |
| `suenoia/wearable/temperature` | `biometrics.temperature` | Temp corporal (°C) |
| `suenoia/wearable/movement` | `biometrics.movement` | Pasos + intensidad |
| `suenoia/wearable/respiration` | `biometrics.respiration` | Respiraciones/min |
| `suenoia/wearable/sleep` | `biometrics.sleep` | Fase de sueño |

## Formato de mensaje

Idéntico a un sample HKQuantitySample exportado desde HealthKit:

```json
{
  "user_id": 1,
  "type": "HKQuantityTypeIdentifierHeartRate",
  "unit": "count/min",
  "value": 64.3,
  "start_date": "2026-05-28T22:30:15+02:00",
  "end_date":   "2026-05-28T22:30:15+02:00",
  "source_name": "SueñoIA Wearable Simulator",
  "source_version": "1.0.0",
  "device": "Apple Watch Series 9 (simulado)",
  "metadata": {
    "phase": "HKCategoryValueSleepAnalysisAsleepDeep"
  }
}
```

Tras pasar por el bridge, llega a Kafka con campos extra:

```json
{
  "...campos anteriores...",
  "metric": "heart_rate",
  "ingested_at": "2026-05-28T20:30:16.123Z",
  "source_topic": "suenoia/wearable/heart_rate",
  "bridge": "mqtt-to-kafka"
}
```
