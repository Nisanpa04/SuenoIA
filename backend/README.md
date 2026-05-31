# 🤖 SueñoIA v2 — Backend FastAPI

API que une todo el sistema:
- **Claude** como coach del sueño (con contexto biométrico real del usuario)
- Lectura de TimescaleDB (biometrías, alertas, diario)
- Persistencia de conversaciones

## Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET    | `/health`                       | Estado del backend, DB y conexión Anthropic |
| GET    | `/`                             | Index de la API |
| POST   | `/chat`                         | Envía un mensaje a Claude (con contexto biométrico inyectado) |
| GET    | `/chat/context/{user_id}`       | Devuelve el contexto que se le pasaría a Claude (debug) |
| GET    | `/chat/history/{user_id}`       | Historial de conversación del usuario |
| POST   | `/chat/journal`                 | Guarda una entrada del diario (mood, estrés, cafeína…) |
| GET    | `/alerts/{user_id}`             | Lista de alertas detectadas por Spark Streaming |

Docs interactivos en: http://localhost:8000/docs

## Instalación

```bash
cd suenoia-v2/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edita .env y pon tu ANTHROPIC_API_KEY real
```

## Arranque

```bash
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

## Pruebas rápidas

### 1) Healthcheck

```bash
curl -s http://localhost:8000/health | python3 -m json.tool
```

Debe devolver `db: true` y `anthropic: true`.

### 2) Ver el contexto biométrico que se le pasa a Claude

```bash
curl -s "http://localhost:8000/chat/context/1?hours_back=6" | python3 -m json.tool
```

Sale el snapshot real del usuario (HR, HRV, fases de sueño, alertas, diario).

### 3) Chatear con Claude

```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
        "user_id": 1,
        "message": "¿Cómo está siendo mi sueño esta noche?",
        "preset": "default"
      }' | python3 -m json.tool
```

Claude responde con datos reales tipo:

> *"En las últimas 6 horas tu HR media ha sido de 64 bpm con HRV de 52 ms, ambos en rango saludable. Tu fase profunda representa el 18% del total, ligeramente por debajo del 20% recomendado. Para mañana intenta acostarte 20 min antes y evitar pantallas 1h antes de dormir."*

### 4) Guardar entrada del diario

```bash
curl -s -X POST http://localhost:8000/chat/journal \
  -H "Content-Type: application/json" \
  -d '{"user_id":1,"mood":7,"stress_level":5,"caffeine_after_17":false,"alcohol":false,"screens_min_before_bed":30,"notes":"Día tranquilo"}'
```

### 5) Listar alertas detectadas

```bash
curl -s http://localhost:8000/alerts/1 | python3 -m json.tool
```

## Modos de conversación

El campo `preset` en `/chat`:
- `"default"` — coach general
- `"pre_sleep"` — rutina previa a dormir (preguntas)
- `"post_sleep"` — rutina al despertar (resumen + recomendaciones)

## Diagrama

```
       Frontend / curl
              │
              ▼ POST /chat {user_id, message}
       ┌──────────────┐
       │   FastAPI    │
       └──┬───────────┘
          │
          ├──→ load_user_context(user_id)
          │    └──→ TimescaleDB (últimas 6h)
          │
          ├──→ format_context_for_claude()
          │
          └──→ Anthropic Claude
                │ system = "coach + contexto"
                │ messages = [...historial, user]
                ▼
          ← respuesta natural con datos reales
                │
                ▼ persist chat_messages
          TimescaleDB
```
