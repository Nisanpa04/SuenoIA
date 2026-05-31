"""
Consumer Kafka que lee `alerts.detected` y dispatcha cada alerta:
  - Broadcast por WebSocket a los clientes del usuario
  - Envío Telegram al chat_id del usuario

Ejecuta el consumer en un thread daemon y usa `asyncio.run_coroutine_threadsafe`
para entrar al event loop principal de FastAPI sin race conditions.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from typing import Optional

from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable

from app.config import settings
from app.services.connection_manager import manager
from app.services.telegram_client import get_user_telegram_chat_id, send_telegram_alert

log = logging.getLogger("alerts-consumer")


class AlertsConsumer:
    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self.stats = {"received": 0, "ws": 0, "telegram": 0}

    # ------------------------------------------------------------------ #
    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True, name="alerts-consumer")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    # ------------------------------------------------------------------ #
    def _build_consumer(self) -> KafkaConsumer:
        return KafkaConsumer(
            settings.kafka_alerts_topic,
            bootstrap_servers=settings.kafka_bootstrap,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            group_id="suenoia-backend",
            auto_offset_reset="latest",
            consumer_timeout_ms=1000,
        )

    # ------------------------------------------------------------------ #
    def _run(self) -> None:
        log.info("📡 Conectando consumer Kafka → topic %s", settings.kafka_alerts_topic)

        # Retry de conexión: arrancar antes que Kafka es posible
        consumer = None
        for attempt in range(10):
            if self._stop.is_set():
                return
            try:
                consumer = self._build_consumer()
                break
            except NoBrokersAvailable:
                log.warning(f"  Kafka no disponible (intento {attempt+1}/10), reintento en 3s")
                time.sleep(3)
        if consumer is None:
            log.error("❌ No se pudo conectar al consumer Kafka. Alertas deshabilitadas.")
            return

        log.info("✅ Alerts consumer en marcha")

        while not self._stop.is_set():
            try:
                for msg in consumer:
                    if self._stop.is_set():
                        break
                    alert = msg.value
                    self.stats["received"] += 1
                    # Lanza la corrutina al loop principal
                    asyncio.run_coroutine_threadsafe(
                        self._dispatch(alert), self.loop,
                    )
            except Exception as e:
                log.warning(f"Consumer error: {e}")
                time.sleep(1)

        try:
            consumer.close()
        except Exception:
            pass
        log.info("👋 Alerts consumer detenido")

    # ------------------------------------------------------------------ #
    async def _dispatch(self, alert: dict) -> None:
        user_id = alert.get("user_id")
        if user_id is None:
            return

        # 1) WebSocket broadcast
        n_ws = await manager.broadcast_to_user(int(user_id), {
            "type": "alert",
            "data": alert,
        })
        if n_ws:
            self.stats["ws"] += n_ws

        # 2) Telegram (si el usuario tiene chat_id configurado)
        try:
            chat_id = get_user_telegram_chat_id(int(user_id))
            if chat_id:
                ok = await send_telegram_alert(chat_id, alert)
                if ok:
                    self.stats["telegram"] += 1
        except Exception as e:
            log.warning(f"Dispatch Telegram falló: {e}")
