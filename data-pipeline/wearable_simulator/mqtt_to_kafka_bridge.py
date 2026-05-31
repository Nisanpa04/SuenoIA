#!/usr/bin/env python3
"""
SueñoIA — Bridge MQTT → Kafka.

Subscribe a todos los topics de wearable en Mosquitto y los publica en
los topics correspondientes de Kafka, añadiendo metadatos de ingesta.

Este componente representa lo que en un sistema real sería un
"IoT gateway" o un "edge broker bridge".

Uso:
    python mqtt_to_kafka_bridge.py
"""

from __future__ import annotations

import json
import signal
import sys
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
MQTT_HOST = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC_FILTER = "suenoia/wearable/+"   # comodín: todas las métricas

KAFKA_BOOTSTRAP = "localhost:19092"
KAFKA_TOPIC_PREFIX = "biometrics"


# Mapeo de tipo HealthKit → nombre corto de métrica (para topic Kafka)
HK_TYPE_TO_METRIC = {
    "HKQuantityTypeIdentifierHeartRate":                "heart_rate",
    "HKQuantityTypeIdentifierHeartRateVariabilitySDNN": "hrv",
    "HKQuantityTypeIdentifierOxygenSaturation":         "oxygen",
    "HKQuantityTypeIdentifierBodyTemperature":          "temperature",
    "HKQuantityTypeIdentifierStepCount":                "movement",
    "HKQuantityTypeIdentifierRespiratoryRate":          "respiration",
    "HKCategoryTypeIdentifierSleepAnalysis":            "sleep",
}


# --------------------------------------------------------------------------- #
# Producer Kafka
# --------------------------------------------------------------------------- #
def build_kafka_producer() -> KafkaProducer:
    print(f"🟢 Conectando a Kafka  {KAFKA_BOOTSTRAP}...")
    try:
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            linger_ms=20,
            compression_type="gzip",
        )
        print("✅ Kafka producer listo")
        return producer
    except NoBrokersAvailable:
        print(f"❌ No se puede conectar a Kafka en {KAFKA_BOOTSTRAP}")
        print("   Comprueba que el contenedor Kafka está arriba:")
        print("   docker compose ps kafka")
        sys.exit(1)


# --------------------------------------------------------------------------- #
# Bridge
# --------------------------------------------------------------------------- #
class Bridge:
    def __init__(self):
        self.producer = build_kafka_producer()
        self.counter = {"total": 0}

        self.mqtt_client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id="suenoia-bridge",
        )
        self.mqtt_client.on_connect = self._on_connect
        self.mqtt_client.on_message = self._on_message

    # ------------------------------------------------------------------ #
    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            print(f"✅ Conectado a MQTT {MQTT_HOST}:{MQTT_PORT}")
            client.subscribe(MQTT_TOPIC_FILTER, qos=0)
            print(f"📡 Subscrito a '{MQTT_TOPIC_FILTER}'\n")
        else:
            print(f"❌ Fallo MQTT (code={reason_code})")

    # ------------------------------------------------------------------ #
    def _on_message(self, client, userdata, mqtt_msg):
        try:
            data = json.loads(mqtt_msg.payload.decode("utf-8"))
        except Exception as e:
            print(f"⚠️  Payload no parseable: {e}")
            return

        hk_type = data.get("type", "unknown")
        metric = HK_TYPE_TO_METRIC.get(hk_type, "unknown")
        kafka_topic = f"{KAFKA_TOPIC_PREFIX}.{metric}"

        # Enriquecemos con metadatos del bridge
        enriched = {
            **data,
            "metric": metric,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
            "source_topic": mqtt_msg.topic,
            "bridge": "mqtt-to-kafka",
        }

        # Clave de partición por user_id (para distribución estable en Kafka)
        key = str(data.get("user_id", "anonymous"))

        self.producer.send(kafka_topic, value=enriched, key=key)
        self.counter["total"] += 1
        self.counter[metric] = self.counter.get(metric, 0) + 1

        # Print resumido cada 50 mensajes
        if self.counter["total"] % 50 == 0:
            metrics_str = " | ".join(
                f"{m}: {n}" for m, n in self.counter.items() if m != "total"
            )
            print(f"📊 {self.counter['total']} msgs → Kafka  ({metrics_str})")

    # ------------------------------------------------------------------ #
    def run(self):
        self.mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
        self.mqtt_client.loop_forever()

    def stop(self):
        print("\n👋 Cerrando bridge...")
        try:
            self.producer.flush(timeout=5)
            self.producer.close()
        except Exception:
            pass
        self.mqtt_client.disconnect()


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    bridge = Bridge()

    def shutdown(signum, frame):
        bridge.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print("🌉 SueñoIA MQTT→Kafka bridge\n")
    print(f"   MQTT  in : {MQTT_HOST}:{MQTT_PORT}  ({MQTT_TOPIC_FILTER})")
    print(f"   Kafka out: {KAFKA_BOOTSTRAP}  ({KAFKA_TOPIC_PREFIX}.*)\n")
    print("   Ctrl+C para detener\n")

    try:
        bridge.run()
    except KeyboardInterrupt:
        shutdown(None, None)


if __name__ == "__main__":
    main()
