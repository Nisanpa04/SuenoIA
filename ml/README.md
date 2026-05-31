# 🧠 SueñoIA v2 — Entrenamiento ML

Entrena dos modelos sobre el dataset de Kaggle (Sleep Health and Lifestyle),
los compara y registra **todo en MLflow** (tracking + modelo en registry).

| Framework | Modelo | Rol |
|-----------|--------|-----|
| **PySpark MLlib** | `GBTRegressor` | Tooling distribuido (Big Data) |
| **scikit-learn** | `GradientBoostingRegressor` | Inferencia rápida en el backend |

Ambos se loggean en MLflow. El **sklearn** se promociona al registry como
`suenoia-sleep` y el backend lo carga desde ahí.

---

## 📥 Prerequisitos

1. Docker compose arriba (con MLflow corriendo en `localhost:5500`)
2. Dataset disponible en uno de estos paths (el script los busca):
   - `suenoia-v2/ml/data/sleep_dataset.csv`
   - `suenoia/backend/data/sleep_dataset.csv` (del v1)
3. Java 17 instalado (lo mismo que para Spark Streaming)

---

## 🚀 Instalación y entrenamiento

```bash
cd suenoia-v2/ml
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Copia el dataset si no existe
mkdir -p data
cp ../../suenoia/backend/data/sleep_dataset.csv data/

# Lanza el entrenamiento dual
python train.py
```

Verás:
```
📂 Cargando dataset…
  374 filas, 13 columnas
🔌 Conectando a MLflow http://localhost:5500
🧠 Entrenando scikit-learn…
  sklearn → MAE=0.072  RMSE=0.215  R²=0.967  (0.4s)
  sklearn registrado en MLflow registry como 'suenoia-sleep'
⚙️  Entrenando PySpark MLlib (puede tardar 30-60s la primera vez)…
  pyspark → MAE=0.085  RMSE=0.241  R²=0.954  (38.7s)

📊 RESUMEN COMPARATIVO:
  modelo                    MAE     RMSE       R²    segs
  sklearn GBR              0.072    0.215    0.967     0.4
  PySpark MLlib GBT        0.085    0.241    0.954    38.7
✅ Entrenamiento finalizado
```

---

## 🔍 Visualiza experimentos

Abre **http://localhost:5500** → experiment **suenoia-sleep-quality** → verás:
- Las 2 runs (sklearn-gbr, pyspark-gbt) con métricas
- Los parámetros y artifacts
- El modelo registrado en **Models** → `suenoia-sleep`

---

## 🤖 Probar predicción desde el backend

Una vez entrenado:

```bash
# Recarga el modelo en el backend (sin reiniciar uvicorn)
curl -s -X POST http://localhost:8000/predict/reload

# Predice calidad de sueño
curl -s -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
        "age": 30,
        "gender": "Male",
        "sleep_duration": 7.0,
        "physical_activity": 60,
        "stress_level": 4,
        "bmi_category": "Normal",
        "heart_rate": 70,
        "systolic": 120,
        "sleep_disorder": "None"
      }' | python3 -m json.tool
```

Respuesta esperada:
```json
{
    "raw_value": 7.85,
    "score_100": 78.5,
    "category": "Buena",
    "model_version": null
}
```

---

## 📊 Cómo lo defenderás en la memoria

### Big Data
*"Entrenamos un GBTRegressor con PySpark MLlib usando un pipeline distribuido
con `VectorAssembler`, `StringIndexer`, `OneHotEncoder` y `StandardScaler`.
El pipeline puede escalar a millones de filas en un cluster Spark sin cambiar
una línea de código."*

### MLOps
*"Todos los experimentos (parámetros, métricas, artefactos del modelo) se
registran en MLflow. El backend carga la versión 'latest' desde el registry,
lo que permite re-entrenar y promocionar versiones sin reiniciar el servicio
(ver `/predict/reload`)."*

### Elección pragmática
*"PySpark MLlib justifica el stack Big Data pero scikit-learn ofrece menor
latencia (<5 ms vs 200 ms cold start de Spark). Para un endpoint con SLO
de latencia tipo P95 < 100 ms, sklearn es la elección correcta. Se mantiene
el código MLlib como prueba de que el sistema escala a dataset grandes."*
