# 🎨 SueñoIA v2 — Frontend React

Frontend Vite + React + Tailwind con **3 pestañas**:

| Tab | Endpoint backend | Función |
|-----|-----------------|---------|
| 🧠 **Predict** | POST `/predict` | Predicción con modelo MLflow Registry |
| 💬 **Chat IA** | POST `/chat` | Coach Claude con contexto biométrico real |
| 📡 **Live** | WS `/ws/alerts/1` + GET `/chat/context/1` | Monitor en vivo de biometrías + stream de alertas |

## Arranque

```bash
cd suenoia-v2/frontend
npm install
npm run dev
```

Abre **http://localhost:5173** automáticamente.

> Requiere el backend (Bloque D-E) corriendo en `http://localhost:8000`.

## Variables de entorno

`.env` (copia `.env.example`):
```
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
```

## Lo que verás

### Tab **Predict**
Formulario clásico → modelo de MLflow Registry → resultado en tarjeta con
score 0-100 y categoría (Insuficiente/Buena/Excelente).

### Tab **Chat IA**
Conversación con Claude. Cada respuesta usa **datos reales** de las últimas
6 horas (HR media, HRV, fases, alertas…). 3 modos: coach general / pre-sueño
/ post-despertar.

### Tab **Live**
- 4 tarjetas con HR/HRV/SpO₂/Temp medias (refresco cada 10 s)
- Barras de distribución de fases de sueño
- Stream de alertas que llegan vía WebSocket (sin polling, push real)
- Link a Grafana para histórico
