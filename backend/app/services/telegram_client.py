"""Cliente Telegram para enviar notificaciones al móvil del usuario."""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.config import settings
from app.db import get_cursor

log = logging.getLogger("telegram")

SEVERITY_EMOJI = {
    "critical": "🚨",
    "warning":  "⚠️",
    "info":     "💡",
}


def get_user_telegram_chat_id(user_id: int) -> Optional[str]:
    """Lee el telegram_chat_id de un usuario desde la BBDD."""
    try:
        with get_cursor() as cur:
            cur.execute(
                "SELECT telegram_chat_id FROM users WHERE id = %s", (user_id,),
            )
            row = cur.fetchone()
            return row["telegram_chat_id"] if row else None
    except Exception as e:
        log.warning(f"No se pudo leer chat_id para user {user_id}: {e}")
        return None


def format_alert(alert: dict) -> str:
    emoji = SEVERITY_EMOJI.get(alert.get("severity"), "📊")
    title = alert.get("title", "Alerta")
    text  = alert.get("text", "")
    metric = alert.get("metric", "")
    value  = alert.get("value", "")

    msg = f"{emoji} *{title}*\n\n{text}"
    if metric:
        msg += f"\n\n_Métrica:_ `{metric}`"
    if value not in ("", None):
        msg += f"\n_Valor:_ `{value}`"
    msg += "\n\n— SueñoIA"
    return msg


async def send_telegram_alert(chat_id: str, alert: dict) -> bool:
    """Envía una alerta formateada vía Telegram Bot API. Devuelve True si OK."""
    if not settings.telegram_bot_token:
        log.debug("TELEGRAM_BOT_TOKEN vacío — skip envío")
        return False
    if not chat_id:
        return False

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": format_alert(alert),
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(url, json=payload)
        if r.status_code != 200:
            log.warning(f"Telegram API {r.status_code}: {r.text}")
            return False
        return True
    except Exception as e:
        log.warning(f"Telegram envío falló: {e}")
        return False
