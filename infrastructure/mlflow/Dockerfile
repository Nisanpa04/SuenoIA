FROM python:3.11-slim

RUN pip install --no-cache-dir \
    mlflow==2.13.0 \
    psycopg2-binary==2.9.9 \
    "setuptools<81"

EXPOSE 5000

# --serve-artifacts hace que MLflow actúe como proxy:
# el cliente sube los artifacts vía HTTP y MLflow los guarda en
# --artifacts-destination (dentro del contenedor). Así no hace falta
# que el cliente pueda escribir directamente en esa ruta.
CMD ["sh", "-c", "mlflow server \
    --host 0.0.0.0 \
    --port 5000 \
    --backend-store-uri $MLFLOW_BACKEND_STORE_URI \
    --artifacts-destination $MLFLOW_ARTIFACTS_DESTINATION \
    --serve-artifacts"]
