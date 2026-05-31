# SueñoIA v2 — Makefile de atajos

.PHONY: up down restart logs ps clean build pull help

help:           ## Muestra los comandos disponibles
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

up:             ## Arranca todos los servicios en background
	docker compose up -d
	@echo ""
	@echo "✅ Servicios arrancando. Espera ~60s la primera vez."
	@echo ""
	@echo "🌐 URLs útiles:"
	@echo "   Kafka UI:      http://localhost:18080"
	@echo "   Node-RED:      http://localhost:11880"
	@echo "   Kibana:        http://localhost:15601"
	@echo "   Grafana:       http://localhost:3001  (admin/admin)"
	@echo "   MLflow:        http://localhost:5500"
	@echo "   Elasticsearch: http://localhost:19200"
	@echo ""

down:           ## Para todos los servicios (mantiene volúmenes)
	docker compose down

restart:        ## Reinicia todos los servicios
	docker compose restart

logs:           ## Logs en tiempo real de todos los servicios
	docker compose logs -f --tail=100

ps:             ## Estado de los servicios
	docker compose ps

clean:          ## ⚠️  Borra contenedores Y volúmenes (resetea todo)
	docker compose down -v
	@echo "💥 Todos los datos persistentes borrados."

build:          ## Reconstruye imágenes locales (MLflow)
	docker compose build

pull:           ## Descarga las últimas versiones de las imágenes
	docker compose pull

es-health:      ## Comprueba salud de Elasticsearch
	curl -s http://localhost:19200/_cluster/health | python3 -m json.tool

kafka-topics:   ## Lista los topics de Kafka
	docker exec suenoia-kafka kafka-topics --bootstrap-server kafka:29092 --list

psql:           ## Abre psql contra TimescaleDB (desde dentro del contenedor)
	docker exec -it suenoia-timescaledb psql -U suenoia -d suenoia

psql-host:      ## Abre psql desde el host (puerto 5433)
	psql -h localhost -p 5433 -U suenoia -d suenoia
