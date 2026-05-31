"""Registro en memoria de conexiones WebSocket por usuario."""
from __future__ import annotations

import logging
from typing import Dict, List

from fastapi import WebSocket

log = logging.getLogger("ws")


class ConnectionManager:
    """Mantiene una lista de WebSockets activos por user_id.

    Cuando llega una alerta, hace broadcast a todos los WebSockets de ese usuario.
    Soporta múltiples conexiones (ej. móvil + escritorio del mismo user).
    """

    def __init__(self) -> None:
        self._active: Dict[int, List[WebSocket]] = {}

    # ------------------------------------------------------------------ #
    async def connect(self, user_id: int, ws: WebSocket) -> None:
        await ws.accept()
        self._active.setdefault(user_id, []).append(ws)
        log.info(f"WS connect  user={user_id}  total={self.total_connections()}")

    def disconnect(self, user_id: int, ws: WebSocket) -> None:
        conns = self._active.get(user_id, [])
        if ws in conns:
            conns.remove(ws)
        if not conns and user_id in self._active:
            del self._active[user_id]
        log.info(f"WS disconnect user={user_id}  total={self.total_connections()}")

    # ------------------------------------------------------------------ #
    async def broadcast_to_user(self, user_id: int, message: dict) -> int:
        """Devuelve cuántos WebSockets recibieron el mensaje."""
        sent = 0
        for ws in list(self._active.get(user_id, [])):
            try:
                await ws.send_json(message)
                sent += 1
            except Exception as e:
                log.warning(f"WS error user={user_id}: {e}")
                self.disconnect(user_id, ws)
        return sent

    # ------------------------------------------------------------------ #
    def total_connections(self) -> int:
        return sum(len(v) for v in self._active.values())


manager = ConnectionManager()
