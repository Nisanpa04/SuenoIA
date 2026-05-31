"""FastAPI app — SueñoIA v2."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app import __version__
from app.routers import alerts, chat, health, predict, test_tools, users, ws
from app.services.alerts_consumer import AlertsConsumer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("main")


# --------------------------------------------------------------------------- #
# Lifespan: arranca/para el consumer de alertas en background
# --------------------------------------------------------------------------- #
@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_running_loop()
    consumer = AlertsConsumer(loop)
    consumer.start()
    app.state.alerts_consumer = consumer
    log.info("🚀 SueñoIA v2 backend listo")
    yield
    log.info("👋 Parando consumer de alertas…")
    consumer.stop()


# --------------------------------------------------------------------------- #
app = FastAPI(
    title="SueñoIA v2 API",
    description=(
        "Backend de la plataforma SueñoIA: IA conversacional con Claude, "
        "lectura de biométricas, alertas y notificaciones en tiempo real."
    ),
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://localhost:3000",
        "http://127.0.0.1:5173", "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(alerts.router)
app.include_router(users.router)
app.include_router(predict.router)
app.include_router(ws.router)
app.include_router(test_tools.router)


# --------------------------------------------------------------------------- #
# Test page del WebSocket (útil sin frontend todavía)
# --------------------------------------------------------------------------- #
_TEST_PAGE = """\
<!doctype html>
<html><head><meta charset="utf-8">
<title>SueñoIA — WS test</title>
<style>
  body { font-family: system-ui, -apple-system, sans-serif; max-width: 780px;
         margin: 40px auto; padding: 20px; color: #1e1b4b; }
  h1 { color: #7c3aed; }
  #log { background: #f5f3ff; border: 1px solid #c4b5fd; border-radius: 8px;
         padding: 12px; height: 480px; overflow-y: auto; font-family: monospace;
         font-size: 13px; white-space: pre-wrap; }
  .alert { border-left: 4px solid #ef4444; padding: 8px 12px; margin: 8px 0;
           background: #fff; border-radius: 4px; }
  .alert.warning { border-color: #f59e0b; }
  .alert.info    { border-color: #3b82f6; }
  .status { font-weight: 600; }
  .status.ok  { color: #10b981; }
  .status.err { color: #ef4444; }
</style></head>
<body>
  <h1>🔔 SueñoIA — Test de alertas WebSocket</h1>
  <p>Estado: <span id="status" class="status">conectando…</span></p>
  <div id="log">Esperando alertas… (genera anomalías con el simulador)</div>
  <script>
    const userId = 1;
    const ws = new WebSocket(`ws://${location.host}/ws/alerts/${userId}`);
    const log = document.getElementById("log");
    const status = document.getElementById("status");
    function append(html) {
      log.innerHTML += html + "\\n";
      log.scrollTop = log.scrollHeight;
    }
    ws.onopen = () => { status.textContent = "conectado"; status.className = "status ok"; };
    ws.onclose = () => { status.textContent = "desconectado"; status.className = "status err"; };
    ws.onerror = () => { status.textContent = "error";       status.className = "status err"; };
    ws.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.type === "alert") {
        const a = m.data;
        append(`<div class="alert ${a.severity}">
          <strong>${a.title}</strong><br>
          ${a.text}<br>
          <small>${a.metric || ""} = ${a.value || ""}</small>
        </div>`);
      } else {
        append(`<i>${ev.data}</i>`);
      }
    };
    // Heartbeat
    setInterval(() => ws.readyState === 1 && ws.send("ping"), 25000);
  </script>
</body></html>
"""


@app.get("/ws-test", response_class=HTMLResponse, tags=["sistema"])
def ws_test_page():
    return _TEST_PAGE


@app.get("/", tags=["sistema"])
def root():
    return {
        "name": "SueñoIA v2 API",
        "version": __version__,
        "docs": "/docs",
        "ws_test": "/ws-test",
        "endpoints": [
            "/health",
            "/chat",
            "/chat/context/{user_id}",
            "/chat/history/{user_id}",
            "/chat/journal",
            "/alerts/{user_id}",
            "/ws/alerts/{user_id}",
        ],
    }
