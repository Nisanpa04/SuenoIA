"""Gestión básica de usuarios + vinculación con Telegram."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db import get_cursor

router = APIRouter(prefix="/users", tags=["usuarios"])


class TelegramLink(BaseModel):
    user_id: int
    telegram_chat_id: str


@router.post("/telegram", status_code=200)
def link_telegram(body: TelegramLink):
    """Vincula un chat_id de Telegram a un usuario de SueñoIA."""
    try:
        with get_cursor() as cur:
            cur.execute(
                "UPDATE users SET telegram_chat_id = %s WHERE id = %s",
                (body.telegram_chat_id, body.user_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Usuario no encontrado")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "ok", "user_id": body.user_id, "chat_id": body.telegram_chat_id}


@router.get("/{user_id}")
def get_user(user_id: int) -> dict:
    with get_cursor() as cur:
        cur.execute(
            "SELECT id, email, name, chronotype, timezone, telegram_chat_id "
            "FROM users WHERE id = %s",
            (user_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return dict(row)
