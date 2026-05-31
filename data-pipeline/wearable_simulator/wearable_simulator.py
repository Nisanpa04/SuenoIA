#!/usr/bin/env python3
"""
SueñoIA — Simulador de Apple Watch / wearable.

Genera lecturas biométricas realistas con patrones día/noche, ciclos
de sueño, anomalías aleatorias, y las publica en MQTT con formato
HealthKit-compatible.

Uso:
    python wearable_simulator.py                # tiempo real (1 segundo = 1s)
    python wearable_simulator.py --speed 60     # acelerado (1s real = 60s simulados)
    python wearable_simulator.py --user-id 1 --speed 120

Topics MQTT:
    suenoia/wearable/heart_rate
    suenoia/wearable/hrv
    suenoia/wearable/oxygen
    suenoia/wearable/temperature
    suenoia/wearable/movement
    suenoia/wearable/sleep
    suenoia/wearable/respiration
"""

from __future__ import annotations

import argparse
import json
import math
import random
import signal
import sys
import time
from datetime import datetime

import numpy as np
import paho.mqtt.client as mqtt

from healthkit_schema import HKSample, HKSleepStage, HKType, HKUnit, make_sample


# --------------------------------------------------------------------------- #
# Configuración
# --------------------------------------------------------------------------- #
MQTT_HOST = "localhost"
MQTT_PORT = 1883
TOPIC_PREFIX = "suenoia/wearable"
PUBLISH_INTERVAL_SEC = 2.0   # cada cuántos segundos reales publica

# Probabilidades de anomalías (para que el Spark Streaming de Bloque C las detecte)
P_HR_SPIKE     = 0.005   # 0.5%
P_LOW_SPO2     = 0.003   # 0.3%
P_WAKE_AT_NIGHT = 0.02   # 2%


# --------------------------------------------------------------------------- #
# Modelo de patrón biométrico
# --------------------------------------------------------------------------- #
class BiometricProfile:
    """Modelo simple del estado fisiológico del usuario a lo largo del día."""

    def __init__(self, user_id: int):
        self.user_id = user_id
        # Características personales constantes
        self.resting_hr = random.uniform(58, 68)        # bpm en reposo
        self.max_hr = 200 - random.uniform(25, 45)       # 220-edad aprox
        self.baseline_hrv = random.uniform(45, 80)       # ms SDNN
        self.baseline_temp = random.uniform(36.4, 36.8)  # °C
        self.stress_level = random.uniform(0.2, 0.5)     # 0=relax, 1=máximo

        # Estado dinámico
        self.cumulative_steps = 0

    # ------------------------------------------------------------------ #
    def phase_at(self, ts: datetime) -> str:
        """Devuelve la fase de sueño esperada según la hora del día."""
        h = ts.hour + ts.minute / 60

        # Despierto durante el día (8h - 23h)
        if 8 <= h < 23:
            return HKSleepStage.AWAKE

        # Ciclos durante la noche: aproximadamente 5 ciclos de 90 min
        # Empieza alineado a las 23:30
        sleep_start_h = 23.5
        elapsed_min = ((h - sleep_start_h) % 24) * 60   # min desde dormirse
        cycle_n = int(elapsed_min // 90)                # qué ciclo
        pos_in_cycle = (elapsed_min % 90) / 90.0        # 0..1 dentro del ciclo

        # Fases tipo: 5% N1, 50% N2 (core), 25% N3 (deep), 20% REM
        # En los primeros ciclos más deep, en los últimos más REM
        deep_weight = max(0.0, 0.45 - cycle_n * 0.08)
        rem_weight  = min(0.45, 0.05 + cycle_n * 0.08)

        if pos_in_cycle < 0.05:
            return HKSleepStage.ASLEEP_CORE   # transición ligera
        elif pos_in_cycle < 0.05 + deep_weight:
            return HKSleepStage.ASLEEP_DEEP
        elif pos_in_cycle < 0.05 + deep_weight + rem_weight:
            return HKSleepStage.ASLEEP_REM
        else:
            return HKSleepStage.ASLEEP_CORE

    # ------------------------------------------------------------------ #
    def heart_rate(self, ts: datetime, phase: str) -> float:
        """HR realista según fase y momento del día."""
        base = self.resting_hr

        # Ritmo circadiano simple (HR mínimo a las 4am)
        circadian = 5 * math.sin((ts.hour - 4) * math.pi / 12)

        # Modificador por fase
        if phase == HKSleepStage.ASLEEP_DEEP:
            mod = -8
        elif phase == HKSleepStage.ASLEEP_REM:
            mod = +3   # HR sube en REM
        elif phase == HKSleepStage.ASLEEP_CORE:
            mod = -4
        elif phase == HKSleepStage.AWAKE and ts.hour > 8:
            mod = 18 + random.uniform(0, 12)  # actividad diaria
        else:
            mod = 0

        # Variabilidad latido a latido
        noise = np.random.normal(0, 2)

        hr = base + circadian + mod + noise

        # Anomalía aleatoria: spike repentino
        if random.random() < P_HR_SPIKE:
            hr += random.uniform(25, 50)

        return float(max(40, min(180, hr)))

    # ------------------------------------------------------------------ #
    def hrv(self, phase: str) -> float:
        """HRV SDNN en ms (más alto = mejor recuperación)."""
        base = self.baseline_hrv
        if phase == HKSleepStage.ASLEEP_DEEP:
            return base * random.uniform(1.10, 1.30)
        if phase == HKSleepStage.ASLEEP_REM:
            return base * random.uniform(0.85, 1.00)
        if phase == HKSleepStage.AWAKE:
            return base * random.uniform(0.55, 0.85)
        return base * random.uniform(0.90, 1.10)

    # ------------------------------------------------------------------ #
    def oxygen_saturation(self) -> float:
        """SpO2 en porcentaje (95-100% sano)."""
        value = np.random.normal(97.5, 0.8)
        if random.random() < P_LOW_SPO2:
            value -= random.uniform(3, 6)
        return float(max(85, min(100, value)))

    # ------------------------------------------------------------------ #
    def body_temperature(self, ts: datetime) -> float:
        """Temperatura corporal (mínimo a las 4am, máximo a las 18h)."""
        circadian = 0.3 * math.sin((ts.hour - 4) * math.pi / 12)
        noise = np.random.normal(0, 0.05)
        return float(self.baseline_temp + circadian + noise)

    # ------------------------------------------------------------------ #
    def movement_intensity(self, phase: str) -> float:
        """Intensidad de movimiento del acelerómetro (0..1)."""
        if phase == HKSleepStage.AWAKE:
            base = random.uniform(0.2, 0.7)
            if random.random() < 0.05:   # picos de ejercicio
                base = random.uniform(0.7, 1.0)
            return base
        if phase == HKSleepStage.ASLEEP_REM:
            return random.uniform(0.0, 0.15)
        return random.uniform(0.0, 0.05)

    # ------------------------------------------------------------------ #
    def steps_delta(self, intensity: float) -> int:
        """Pasos en este intervalo a partir de la intensidad."""
        if intensity < 0.2:
            return 0
        return int(intensity * random.uniform(8, 16))

    # ------------------------------------------------------------------ #
    def respiratory_rate(self, phase: str) -> float:
        """Respiraciones por minuto."""
        if phase == HKSleepStage.ASLEEP_DEEP:
            return random.uniform(11, 14)
        if phase == HKSleepStage.AWAKE:
            return random.uniform(14, 20)
        return random.uniform(12, 16)


# --------------------------------------------------------------------------- #
# Cliente MQTT
# --------------------------------------------------------------------------- #
class WearableSimulator:
    def __init__(self, user_id: int, host: str, port: int):
        self.user_id = user_id
        self.profile = BiometricProfile(user_id)

        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"wearable-sim-user{user_id}",
        )
        self.client.on_connect    = self._on_connect
        self.client.on_disconnect = self._on_disconnect

        print(f"🔌 Conectando a MQTT {host}:{port}...")
        self.client.connect(host, port, keepalive=60)
        self.client.loop_start()

    # ------------------------------------------------------------------ #
    def _on_connect(self, client, userdata, flags, reason_code, properties):
        print(f"✅ Conectado a MQTT  (user_id={self.user_id}, perfil generado)")
        print(f"   HR reposo: {self.profile.resting_hr:.1f} bpm")
        print(f"   HRV base:  {self.profile.baseline_hrv:.1f} ms")
        print(f"   Temp base: {self.profile.baseline_temp:.2f} °C")

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        print(f"⚠️  Desconectado MQTT (code={reason_code})")

    # ------------------------------------------------------------------ #
    def publish(self, sample: HKSample):
        # El topic se deriva del tipo de sample
        type_to_topic = {
            HKType.HEART_RATE:        f"{TOPIC_PREFIX}/heart_rate",
            HKType.HRV_SDNN:          f"{TOPIC_PREFIX}/hrv",
            HKType.OXYGEN_SATURATION: f"{TOPIC_PREFIX}/oxygen",
            HKType.BODY_TEMPERATURE:  f"{TOPIC_PREFIX}/temperature",
            HKType.STEP_COUNT:        f"{TOPIC_PREFIX}/movement",
            HKType.RESPIRATORY_RATE:  f"{TOPIC_PREFIX}/respiration",
            HKType.SLEEP_ANALYSIS:    f"{TOPIC_PREFIX}/sleep",
        }
        topic = type_to_topic.get(sample.type, f"{TOPIC_PREFIX}/unknown")
        payload = json.dumps(sample.to_dict())
        self.client.publish(topic, payload, qos=0)

    # ------------------------------------------------------------------ #
    def tick(self, sim_time: datetime):
        """Genera todas las lecturas para un instante simulado."""
        phase = self.profile.phase_at(sim_time)

        # --- Heart rate ---
        hr = self.profile.heart_rate(sim_time, phase)
        self.publish(make_sample(
            self.user_id, HKType.HEART_RATE, HKUnit.BPM, hr,
            metadata={"phase": phase},
        ))

        # --- HRV (no en cada tick: cada 30s aprox) ---
        if random.random() < 0.15:
            hrv = self.profile.hrv(phase)
            self.publish(make_sample(
                self.user_id, HKType.HRV_SDNN, HKUnit.MS, hrv,
                metadata={"phase": phase},
            ))

        # --- SpO2 (poco frecuente, cada minuto aprox) ---
        if random.random() < 0.05:
            spo2 = self.profile.oxygen_saturation()
            self.publish(make_sample(
                self.user_id, HKType.OXYGEN_SATURATION, HKUnit.PERCENT, spo2,
                metadata={"phase": phase},
            ))

        # --- Temperatura corporal ---
        if random.random() < 0.10:
            temp = self.profile.body_temperature(sim_time)
            self.publish(make_sample(
                self.user_id, HKType.BODY_TEMPERATURE, HKUnit.CELSIUS, temp,
                metadata={"phase": phase},
            ))

        # --- Movimiento (pasos) ---
        intensity = self.profile.movement_intensity(phase)
        steps = self.profile.steps_delta(intensity)
        self.profile.cumulative_steps += steps
        self.publish(make_sample(
            self.user_id, HKType.STEP_COUNT, HKUnit.COUNT, steps,
            metadata={
                "phase": phase,
                "intensity": round(intensity, 3),
                "cumulative": self.profile.cumulative_steps,
            },
        ))

        # --- Respiración (cada minuto) ---
        if random.random() < 0.05:
            rr = self.profile.respiratory_rate(phase)
            self.publish(make_sample(
                self.user_id, HKType.RESPIRATORY_RATE, HKUnit.BREATHS_PM, rr,
                metadata={"phase": phase},
            ))

        # --- Sleep analysis (solo cuando hay cambio relevante) ---
        if random.random() < 0.05:
            self.publish(make_sample(
                self.user_id, HKType.SLEEP_ANALYSIS, HKUnit.COUNT,
                value=1, metadata={"stage": phase},
            ))

    # ------------------------------------------------------------------ #
    def stop(self):
        print("\n👋 Cerrando conexión MQTT...")
        self.client.loop_stop()
        self.client.disconnect()


# --------------------------------------------------------------------------- #
# Main loop
# --------------------------------------------------------------------------- #
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=MQTT_HOST)
    parser.add_argument("--port", type=int, default=MQTT_PORT)
    parser.add_argument("--user-id", type=int, default=1)
    parser.add_argument("--speed", type=float, default=1.0,
                        help="Multiplicador de velocidad (1 = tiempo real, "
                             "60 = 1s real son 60s simulados)")
    parser.add_argument("--start-hour", type=float, default=None,
                        help="Hora simulada de inicio (0-24)")
    args = parser.parse_args()

    sim = WearableSimulator(args.user_id, args.host, args.port)

    # Hora simulada que avanza
    if args.start_hour is not None:
        sim_time = datetime.now().replace(
            hour=int(args.start_hour),
            minute=int((args.start_hour % 1) * 60),
            second=0, microsecond=0,
        )
    else:
        sim_time = datetime.now()

    def shutdown(signum, frame):
        sim.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print(f"📡 Simulando wearable (speed x{args.speed})")
    print(f"   Hora simulada de inicio: {sim_time.strftime('%H:%M')}")
    print(f"   Pulsa Ctrl+C para detener\n")

    last_print = time.time()

    try:
        while True:
            sim.tick(sim_time)

            # Avanza el tiempo simulado
            sim_time = datetime.fromtimestamp(
                sim_time.timestamp() + PUBLISH_INTERVAL_SEC * args.speed
            )

            # Print resumido cada 10 segundos
            if time.time() - last_print > 10:
                phase = sim.profile.phase_at(sim_time)
                print(f"⏱️  {sim_time.strftime('%H:%M')} | "
                      f"fase: {phase.split('Analysis')[-1]:<10} | "
                      f"pasos acumulados: {sim.profile.cumulative_steps}")
                last_print = time.time()

            time.sleep(PUBLISH_INTERVAL_SEC)
    except KeyboardInterrupt:
        shutdown(None, None)


if __name__ == "__main__":
    main()
