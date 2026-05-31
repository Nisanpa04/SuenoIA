# 📊 Dashboards de Grafana — SueñoIA v2

Dashboards auto-provisionados (no hace falta importarlos a mano).

## Dashboards

| Dashboard | UID | Fuente | Qué muestra |
|-----------|-----|--------|-------------|
| 🌙 **SueñoIA — Live Monitoring** | `suenoia-live` | TimescaleDB | HR, HRV, SpO₂, temperatura, fases de sueño, alertas |
| 🚨 **SueñoIA — Alerts Center** | `suenoia-alerts` | TimescaleDB | Timeline de alertas, severidad, categorías, detalle |

## Datasources

- **TimescaleDB** (default) → `timescaledb:5432/suenoia`
- **Elasticsearch** → `http://elasticsearch:9200`, índice `biometrics-*`

Ambos se cargan vía `provisioning/datasources/datasources.yml`.

## Cómo ver los dashboards

1. Abre **http://localhost:3001**
2. Login: `admin / admin` (te pedirá cambiar la contraseña la 1ª vez — pon lo que quieras)
3. Menú lateral → **Dashboards** → carpeta **SueñoIA**
4. Click en el que quieras

## Refresco

Cada panel se autorefresca cada **5 segundos**. Con el simulador corriendo
verás los datos avanzando en vivo.

## Si cambias un dashboard

1. Edita en la UI
2. **Save dashboard** → activa el JSON model y cópialo
3. Reemplaza el JSON correspondiente en `infrastructure/grafana/provisioning/dashboards/`
4. Commit

## Si no aparecen los dashboards

```bash
# Reinicia Grafana para que recargue la provisioning
docker compose restart grafana

# Espera 10s y mira los logs
docker compose logs grafana --tail=30 | grep -i 'provisioning'
```
