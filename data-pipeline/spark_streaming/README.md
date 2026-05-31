# ⚡ Spark Structured Streaming — pipeline en tiempo real

Pipeline de procesamiento distribuido que consume todos los topics
`biometrics.*` de Kafka y mantiene **tres queries en paralelo** sobre el
mismo stream:

| # | Query | Trigger | Salida |
|---|-------|---------|--------|
| 1 | **Raw** | cada 2 s | Elasticsearch (`biometrics-YYYY-MM-DD`) + TimescaleDB (`biometrics`) + reglas → alertas |
| 2 | **Agg 5 min** (avg/min/max/count por user+metric) | cada 10 s | Elasticsearch (`biometrics-agg-YYYY-MM-DD`) |
| 3 | **Anomaly rules** (HR alta dormido, SpO2 baja, HRV baja, fiebre) | mismo batch que raw | Kafka topic `alerts.detected` + tabla `alerts` |

---

## 🍎 Pre-requisito: Java 17 instalado

Spark necesita Java. En tu M2 Pro:

```bash
# Comprueba si ya tienes Java
java -version

# Si no tienes, instálalo:
brew install openjdk@17

# Symlink para que el sistema lo encuentre
sudo ln -sfn /opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk \
            /Library/Java/JavaVirtualMachines/openjdk-17.jdk

# Verifica
java -version
# debe decir: openjdk version "17.x.x"
```

Si Java sigue sin detectarse, añade a tu `~/.zshrc`:

```bash
echo 'export JAVA_HOME=$(/usr/libexec/java_home -v 17)' >> ~/.zshrc
echo 'export PATH=$JAVA_HOME/bin:$PATH' >> ~/.zshrc
source ~/.zshrc
```

---

## 🐍 Instalación del entorno Python

```bash
cd "/Users/nicolassanchezpalomo/Documents/Claude/Projects/Proyecto IA y Big Data/suenoia-v2/data-pipeline/spark_streaming"

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Eso instala **PySpark 3.5.0** (~330 MB), `elasticsearch`, `psycopg2-binary` y `kafka-python-ng`.

---

## ▶️ Arranque

> ⚠️ Importante: el docker-compose (Kafka, Elasticsearch, TimescaleDB) tiene que estar arriba, y el **simulador + bridge** del Bloque B también deben estar publicando.

```bash
source venv/bin/activate
python streaming_job.py
```

La **primera vez** Spark descarga el paquete `spark-sql-kafka-0-10_2.12:3.5.0` (~50 MB). Tarda 1-2 minutos, es normal.

Verás:

```
2026-05-28 ... INFO streaming: 📡 Suscribiéndose a topics Kafka 'biometrics\..*'
2026-05-28 ... INFO streaming: ✅ Query RAW iniciada
2026-05-28 ... INFO streaming: ✅ Query AGG iniciada
2026-05-28 ... INFO streaming: 🚀 Pipeline arrancado. Ctrl+C para parar.
2026-05-28 ... INFO streaming: [batch 0] raw  → 8 filas
2026-05-28 ... INFO streaming: [batch 1] raw  → 12 filas
2026-05-28 ... WARN streaming: [batch 5] 🚨 1 alertas detectadas
2026-05-28 ... INFO streaming: [batch 6] agg  → 3 ventanas
```

> ¡Las alertas saldrán cuando el simulador inyecte una anomalía (probabilidad 0.5% para HR spike, 0.3% para SpO2 baja). Para verlas más rápido puedes aumentar la velocidad del simulador con `--speed 480`.

---

## 🧪 Verifica que los datos llegan a los tres sinks

### 1. Elasticsearch

```bash
curl -s "http://localhost:19200/_cat/indices?v" | grep biometrics
```

Debe listar índices `biometrics-2026-05-28` y `biometrics-agg-2026-05-28`.

Ver mensajes:
```bash
curl -s "http://localhost:19200/biometrics-*/_search?size=3&pretty" | head -80
```

### 2. TimescaleDB

```bash
docker exec -it suenoia-timescaledb psql -U suenoia -d suenoia -c \
  "SELECT metric, COUNT(*) FROM biometrics GROUP BY metric ORDER BY 2 DESC;"
```

Debe mostrar las métricas con sus conteos crecientes.

Ver alertas:
```bash
docker exec -it suenoia-timescaledb psql -U suenoia -d suenoia -c \
  "SELECT created_at, severity, title FROM alerts ORDER BY created_at DESC LIMIT 5;"
```

### 3. Kafka topic de alertas

Abre Kafka UI: http://localhost:18080 → Topics → `alerts.detected` → Messages.

---

## 🧱 Arquitectura del job

```
              Kafka (biometrics.*)
                      │
                      ▼
       ┌──────────────────────────────┐
       │      Spark Streaming         │
       │   readStream subscribePattern│
       │   parse JSON                 │
       └────────────┬─────────────────┘
                    │
        ┌───────────┼───────────────────────┐
        │           │                       │
        ▼           ▼                       ▼
   Query RAW    Query AGG (window 5m)
   trigger 2s   trigger 10s
        │           │
        ▼           ▼
   foreachBatch  foreachBatch
        │           │
        ├──→ ES raw                ├──→ ES agg
        ├──→ TimescaleDB biometrics
        ├──→ detect_anomalies()
        │    └──→ Kafka alerts.detected
        │    └──→ TimescaleDB alerts
```

---

## 🛟 Troubleshooting

| Síntoma | Solución |
|---------|----------|
| `JAVA_HOME not set` | Sigue los pasos de Java arriba |
| `Failed to find data source: kafka` | Internet caído, no descarga el paquete. Reintenta o desactiva el VPN |
| `org.postgresql.util.PSQLException: connect timeout` | TimescaleDB no responde en `localhost:5433`. `docker compose ps timescaledb` |
| Spark se queda colgado en "Resolving dependencies" | Espera, primera vez descarga 50 MB |
| `[batch 0] raw → 0 filas` siempre | El simulador + bridge del Bloque B no están corriendo |
| Error de versión de Java | Spark 3.5 funciona con Java 8/11/17 — no uses 21+ |

---

## 🎯 Qué hemos conseguido

✅ **Tres queries Spark simultáneas** sobre un único stream (algo que Marc no tiene)
✅ **Watermark de 1 minuto** para ventanas con late data
✅ **Triple sink** Elasticsearch + TimescaleDB + Kafka — patrón clásico de data engineering
✅ **Reglas de anomalía con base clínica** (HR, SpO2, HRV, temperatura) — defensible
✅ **Alertas que vuelven al broker Kafka** — listas para que el backend las consuma vía WebSocket o Telegram
✅ **Hypertables de TimescaleDB** = consultas históricas eficientes para Grafana
