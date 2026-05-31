# 🌙 SueñoIA v2 — Plataforma IoT de salud del sueño

> Ecosistema inteligente con ingestión en tiempo real desde wearables,
> Big Data tooling, IA predictiva, IA conversacional y notificaciones
> multi-canal (web + Telegram).

Proyecto académico para el grado de **IA y Big Data** (curso 2025/26).
Autor: **Nicolás Sánchez Palomo**.

---

## 🎯 Visión del ecosistema (3 fases)

| Fase | Cobertura | Estado |
|------|-----------|--------|
| **Fase 1 — Backbone** (lo que entregamos) | Ingesta IoT simulada + Big Data + ML + IA conversacional + dashboards + notificaciones | 🔄 En desarrollo |
| **Fase 2 — App iOS nativa** | Swift/SwiftUI + HealthKit + APNs + sincronización | 📋 Diseñada, no implementada |
| **Fase 3 — Dispositivo físico** | Raspberry Pi + sensores ambientales (luz, ruido, temperatura, CO₂) | 📋 Diseñada, no implementada |

La Fase 1 incluye **simuladores HealthKit-compatible y Raspberry Pi-compatible** que validan el contrato de datos. Las Fases 2 y 3 sustituyen los simuladores sin tocar el backend.

---

## 🧱 Stack de la Fase 1

| Capa | Servicio | Imagen Docker | Puerto |
|------|----------|---------------|--------|
| Coordinación Kafka | Zookeeper | `confluentinc/cp-zookeeper` | 2181 |
| Mensajería | Apache Kafka | `confluentinc/cp-kafka` | 9092 |
| Debug Kafka | Kafka UI | `provectuslabs/kafka-ui` | 8080 |
| Broker IoT | Mosquitto MQTT | `eclipse-mosquitto` | 1883, 9001 |
| Gateway IoT | Node-RED | `nodered/node-red` | 1880 |
| Búsqueda | Elasticsearch 8 | `elasticsearch:8.13.4` | 9200 |
| UI Elastic | Kibana 8 | `kibana:8.13.4` | 5601 |
| Dashboards | Grafana | `grafana/grafana` | 3001 |
| Time-series DB | TimescaleDB (Pg 16) | `timescale/timescaledb` | 5432 |
| ML tracking | MLflow | (build local) | 5500 |

Más adelante se unirán:
- **Backend FastAPI** (puerto 8000)
- **Frontend React** (puerto 5173)
- **Simulador wearable** (proceso Python)
- **Spark Streaming** (proceso Python)

Total RAM estimada: **~6 GB**. Tu Mac M2 Pro sobra.

---

## 🚀 Cómo arrancar

```bash
cd suenoia-v2
make up         # arranca todos los servicios
make ps         # ver estado
make logs       # ver logs
make down       # parar todo
```

O directamente:

```bash
docker compose up -d
```

La primera vez tarda **~5-10 minutos** descargando las imágenes (unos 3 GB).

---

## 🔍 URLs útiles (cuando esté todo arriba)

| URL | Servicio | Login |
|-----|----------|-------|
| http://localhost:18080 | **Kafka UI** — ver topics y mensajes | — |
| http://localhost:11880 | **Node-RED** — flujos visuales IoT | — |
| http://localhost:15601 | **Kibana** — explorar Elasticsearch | — |
| http://localhost:3001 | **Grafana** — dashboards | `admin / admin` |
| http://localhost:5500 | **MLflow** — experimentos ML | — |
| http://localhost:19200 | **Elasticsearch API** | — |
| `localhost:5433`     | **TimescaleDB** | `suenoia / suenoia_pass` |
| `localhost:1883`     | **Mosquitto MQTT** (broker) | — |
| `localhost:19092`    | **Kafka** (bootstrap servers desde host) | — |

> ℹ️ Hemos movido todos los puertos estándar a no-estándar para evitar conflictos con otros servicios de tu Mac. Internamente entre contenedores siguen los puertos normales.

---

## 📂 Estructura

```
suenoia-v2/
├── README.md
├── Makefile
├── docker-compose.yml
├── .env
├── .gitignore
│
├── infrastructure/
│   ├── mosquitto/mosquitto.conf
│   ├── nodered/                  # flujos exportados (más adelante)
│   ├── grafana/provisioning/
│   ├── timescaledb/init.sql      # tablas time-series
│   └── mlflow/Dockerfile
│
├── data-pipeline/                # Bloque B y C — más adelante
├── backend/                      # Bloque D-F — más adelante
└── frontend/                     # Bloque H — más adelante
```

---

## 🗺️ Hoja de ruta 

- [x] **Bloque A** — Infraestructura Docker 
- [ ] Bloque B — Simulador HealthKit 
- [ ] Bloque C — Spark Streaming + ingesta Elasticsearch 
- [ ] Bloque D — IA conversacional (Anthropic API) 
- [ ] Bloque E — Notificaciones tiempo real (WebSocket + Telegram bot) 
- [ ] Bloque F — ML con PySpark MLlib (
- [ ] Bloque G — Dashboards Grafana 
- [ ] Bloque H — Frontend + integración 
- [ ] Bloque I — Memoria académica   
