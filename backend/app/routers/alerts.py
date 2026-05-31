"""Listado de alertas detectadas por Spark Streaming."""
from fastapi import APIRouter

from app.db import get_cursor

router = APIRouter(prefix="/alerts", tags=["alertas"])


@router.get("/{user_id}")
def list_alerts(user_id: int, limit: int = 30) -> list[dict]:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, created_at, severity, category, title, text, metadata
            FROM alerts
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (user_id, limit),
        )
        rows = cur.fetchall()
    return [
        dict(r, created_at=r["created_at"].isoformat())
        for r in rows
    ]
