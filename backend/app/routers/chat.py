"""Endpoint de IA conversacional."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.db import get_cursor
from app.schemas import ChatRequest, ChatResponse, ChatUsage, JournalEntry, UserContext
from app.services.claude_client import chat as claude_chat
from app.services.context_loader import load_user_context

log = logging.getLogger("router.chat")
router = APIRouter(prefix="/chat", tags=["ia"])


@router.post("", response_model=ChatResponse)
def post_chat(req: ChatRequest) -> ChatResponse:
    # 1) Compón el historial Anthropic
    messages = [{"role": m.role, "content": m.content} for m in req.history]
    messages.append({"role": "user", "content": req.message})

    # 2) Llama a Claude
    try:
        result = claude_chat(
            user_id=req.user_id,
            messages=messages,
            preset=req.preset,
            include_context=req.include_context,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        log.exception("Claude error")
        raise HTTPException(status_code=500, detail=f"Claude error: {e}")

    # 3) Persiste el turno en BBDD
    session_id = str(uuid.uuid4())
    try:
        with get_cursor() as cur:
            cur.execute(
                "INSERT INTO chat_messages (user_id, role, content, session_id) "
                "VALUES (%s, 'user', %s, %s)",
                (req.user_id, req.message, session_id),
            )
            cur.execute(
                "INSERT INTO chat_messages (user_id, role, content, session_id) "
                "VALUES (%s, 'assistant', %s, %s)",
                (req.user_id, result["text"], session_id),
            )
    except Exception as e:
        log.warning(f"No se pudo persistir el chat: {e}")

    return ChatResponse(
        text=result["text"],
        model=result["model"],
        usage=ChatUsage(**result["usage"]),
        stop_reason=result["stop_reason"],
    )


@router.get("/context/{user_id}", response_model=UserContext)
def get_context(user_id: int, hours_back: int = 6) -> UserContext:
    """Devuelve el contexto biométrico que se le pasaría a Claude. Útil para debug."""
    ctx = load_user_context(user_id, hours_back=hours_back)
    return UserContext(**ctx)


@router.get("/history/{user_id}")
def get_chat_history(user_id: int, limit: int = 50) -> list[dict]:
    """Devuelve los últimos mensajes del chat de un usuario."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, role, content, created_at, session_id
            FROM chat_messages
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (user_id, limit),
        )
        rows = cur.fetchall()
    # Devolvemos oldest first
    return [dict(r, created_at=r["created_at"].isoformat()) for r in reversed(rows)]


@router.post("/journal", status_code=201)
def post_journal(entry: JournalEntry):
    """Guarda la entrada del diario del usuario (mood, stress, cafeína...)."""
    today = datetime.now(timezone.utc).date()
    try:
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO sleep_journal
                  (user_id, entry_date, mood, stress_level, caffeine_after_17,
                   alcohol, screens_min_before_bed, notes)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (user_id, entry_date) DO UPDATE SET
                    mood = EXCLUDED.mood,
                    stress_level = EXCLUDED.stress_level,
                    caffeine_after_17 = EXCLUDED.caffeine_after_17,
                    alcohol = EXCLUDED.alcohol,
                    screens_min_before_bed = EXCLUDED.screens_min_before_bed,
                    notes = EXCLUDED.notes
                """,
                (
                    entry.user_id, today, entry.mood, entry.stress_level,
                    entry.caffeine_after_17, entry.alcohol,
                    entry.screens_min_before_bed, entry.notes,
                ),
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "ok", "date": today.isoformat()}
