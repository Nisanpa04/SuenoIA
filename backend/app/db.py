"""Conexión simple a TimescaleDB usando psycopg2 con pool básico."""
from contextlib import contextmanager
import psycopg2
import psycopg2.extras

from app.config import settings

# Pool sencillo (sin pgbouncer porque es proyecto académico)
_pool = None


def _connect():
    return psycopg2.connect(settings.pg_dsn)


@contextmanager
def get_cursor(dict_cursor: bool = True):
    """Context manager que cede un cursor (RealDict por defecto)."""
    conn = _connect()
    try:
        cursor_factory = psycopg2.extras.RealDictCursor if dict_cursor else None
        with conn.cursor(cursor_factory=cursor_factory) as cur:
            yield cur
        conn.commit()
    finally:
        conn.close()
