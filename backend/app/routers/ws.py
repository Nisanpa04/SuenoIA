"""Endpoint WebSocket para alertas en tiempo real."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.connection_manager import manager

log = logging.getLogger("router.ws")
router = APIRouter(tags=["websocket"])


@router.websocket("/ws/alerts/{user_id}")
async def ws_alerts(websocket: WebSocket, user_id: int):
    """
    Canal WebSocket para que el frontend reciba alertas en tiempo real.

    Mensajes que el server envía al cliente:
      { "type": "welcome", "user_id": 1, "ts": "..." }
      { "type": "ping", "ts": "..." }
      { "type": "alert", "data": { ...alerta detectada... } }
    """
    await manager.connect(user_id, websocket)
    try:
        # Mensaje de bienvenida
        await websocket.send_json({
            "type": "welcome",
            "user_id": user_id,
            "ts": datetime.now(timezone.utc).isoformat(),
        })

        # El loop principal solo escucha mensajes del cliente; las alertas
        # llegan vía el consumer Kafka en background.
        while True:
            text = await websocket.receive_text()
            # Permitimos un "ping" desde el cliente para mantener vivo el socket
            if text and text.strip().lower() in {"ping", '"ping"'}:
                await websocket.send_json({
                    "type": "pong",
                    "ts": datetime.now(timezone.utc).isoformat(),
                })
    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)
