"""Healthcheck del backend."""
from fastapi import APIRouter

from app import __version__
from app.config import settings
from app.db import get_cursor
from app.schemas import HealthResponse

router = APIRouter(tags=["sistema"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    # DB ping
    db_ok = False
    try:
        with get_cursor(dict_cursor=False) as cur:
            cur.execute("SELECT 1")
            db_ok = cur.fetchone() == (1,)
    except Exception:
        db_ok = False

    return HealthResponse(
        status="ok" if db_ok else "degraded",
        version=__version__,
        db=db_ok,
        anthropic=bool(settings.anthropic_api_key),
    )
