"""
Endpoints de DIAGNÓSTICO. Sirven para verificar el pipeline de alertas
sin tener que esperar a que el simulador genere una anomalía real.

NO usar en producción.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from kafka import KafkaProducer

from app.config import settings
from app.db import get_cursor
from app.services.telegram_client import (
    format_alert, get_user_telegram_chat_id, send_telegram_alert,
)

log = logging.getLogger("router.test")
router = APIRouter(prefix="/test", tags=["debug"])


# --------------------------------------------------------------------------- #
@router.get("/telegram-status")
def telegram_status() -> dict:
    """Comprueba la config Telegram: token cargado + chat_id del usuario 1."""
    chat_id = get_user_telegram_chat_id(1)
    return {
        "token_configured": bool(settings.telegram_bot_token),
        "token_preview": (
            settings.telegram_bot_token[:10] + "..."
            if settings.telegram_bot_token else None
        ),
        "user_1_chat_id": chat_id,
        "ready_to_send": bool(settings.telegram_bot_token and chat_id),
    }


# --------------------------------------------------------------------------- #
@router.post("/telegram")
async def test_telegram(user_id: int = 1) -> dict:
    """
    Envía un mensaje de prueba a Telegram, SIN pasar por Kafka.
    Útil para aislar si el problema es Telegram o el pipeline.
    """
    if not settings.telegram_bot_token:
        raise HTTPException(
            status_code=400,
            detail="TELEGRAM_BOT_TOKEN vacío. Edita backend/.env y reinicia uvicorn.",
        )
    chat_id = get_user_telegram_chat_id(user_id)
    if not chat_id:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Usuario {user_id} no tiene telegram_chat_id. "
                f"Llama a POST /users/telegram para vincularlo."
            ),
        )

    fake_alert = {
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "severity": "info",
        "category": "test",
        "title": "🧪 Mensaje de prueba",
        "text": "Si lees esto, Telegram funciona correctamente.",
        "metric": "test",
        "value": 42,
    }

    ok = await send_telegram_alert(chat_id, fake_alert)
    return {
        "sent": ok,
        "chat_id": chat_id,
        "preview": format_alert(fake_alert),
    }


# --------------------------------------------------------------------------- #
@router.post("/alert")
def publish_fake_alert(user_id: int = 1, severity: str = "warning") -> dict:
    """
    Publica una alerta SINTÉTICA a Kafka, que pasará por todo el pipeline:
    backend consumer → WebSocket + Telegram + persistir en DB.

    Útil para test end-to-end sin esperar al simulador.
    """
    fake = {
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "severity": severity,
        "category": "test",
        "title": f"🧪 Alerta de test ({severity})",
        "text": "Alerta inyectada manualmente para verificar el pipeline.",
        "metric": "heart_rate",
        "value": 999,
    }

    try:
        producer = KafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
        )
        producer.send(settings.kafka_alerts_topic, value=fake, key=str(user_id))
        producer.flush(timeout=5)
        producer.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Kafka error: {e}")

    return {"published": True, "topic": settings.kafka_alerts_topic, "alert": fake}


# --------------------------------------------------------------------------- #
@router.get("/pipeline-status")
def pipeline_status() -> dict:
    """Diagnóstico rápido de todo el pipeline."""
    out = {
        "kafka_alerts_topic": settings.kafka_alerts_topic,
        "telegram": telegram_status(),
        "alerts_in_db": None,
    }
    try:
        with get_cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM alerts;")
            out["alerts_in_db"] = cur.fetchone()["n"]
    except Exception as e:
        out["alerts_in_db_error"] = str(e)
    return out
