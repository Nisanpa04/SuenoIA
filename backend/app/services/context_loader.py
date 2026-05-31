"""
Carga el contexto biométrico actual del usuario para pasárselo a Claude.

Devuelve un resumen estructurado de las últimas N horas:
  - Estadísticos de HR, HRV, SpO2, temperatura
  - Distribución de fases de sueño
  - Alertas recientes (anomalías detectadas por Spark)
  - Última entrada del diario de sueño (mood, stress, cafeína)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.db import get_cursor


def _safe_round(x, n=1):
    return round(x, n) if x is not None else None


def load_user_context(user_id: int, hours_back: int = 6) -> dict[str, Any]:
    """Devuelve un snapshot agregado del estado del usuario."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours_back)

    ctx: dict[str, Any] = {
        "user_id": user_id,
        "window_hours": hours_back,
        "now": datetime.now(timezone.utc).isoformat(),
        "biometrics": {},
        "sleep_phases": {},
        "recent_alerts": [],
        "journal": None,
    }

    with get_cursor() as cur:
        # ----- Usuario base -----
        cur.execute(
            "SELECT name, chronotype, timezone FROM users WHERE id = %s",
            (user_id,),
        )
        user_row = cur.fetchone()
        if user_row:
            ctx["user"] = dict(user_row)

        # ----- Resúmenes por métrica -----
        cur.execute(
            """
            SELECT metric,
                   COUNT(*)             AS n,
                   AVG(value)           AS avg_v,
                   MIN(value)           AS min_v,
                   MAX(value)           AS max_v,
                   PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY value) AS median_v
            FROM biometrics
            WHERE user_id = %s
              AND time   >= %s
              AND metric IN ('heart_rate','hrv','oxygen','temperature','respiration')
            GROUP BY metric
            """,
            (user_id, since),
        )
        for row in cur.fetchall():
            ctx["biometrics"][row["metric"]] = {
                "n_samples": row["n"],
                "avg":    _safe_round(row["avg_v"], 1),
                "min":    _safe_round(row["min_v"], 1),
                "max":    _safe_round(row["max_v"], 1),
                "median": _safe_round(row["median_v"], 1),
            }

        # ----- Distribución de fases de sueño -----
        cur.execute(
            """
            SELECT metadata->>'phase' AS phase, COUNT(*) AS n
            FROM biometrics
            WHERE user_id = %s
              AND time   >= %s
              AND metadata ? 'phase'
            GROUP BY metadata->>'phase'
            """,
            (user_id, since),
        )
        phase_rows = cur.fetchall()
        total = sum(r["n"] for r in phase_rows)
        if total > 0:
            for r in phase_rows:
                short = r["phase"].split("Analysis")[-1]   # 'AsleepDeep', 'Awake'…
                ctx["sleep_phases"][short] = {
                    "n": r["n"],
                    "pct": round(100 * r["n"] / total, 1),
                }

        # ----- Alertas recientes -----
        cur.execute(
            """
            SELECT created_at, severity, category, title, text
            FROM alerts
            WHERE user_id = %s
              AND created_at >= %s
            ORDER BY created_at DESC
            LIMIT 10
            """,
            (user_id, since),
        )
        for row in cur.fetchall():
            ctx["recent_alerts"].append({
                "created_at": row["created_at"].isoformat(),
                "severity": row["severity"],
                "category": row["category"],
                "title": row["title"],
                "text": row["text"],
            })

        # ----- Último diario -----
        cur.execute(
            """
            SELECT entry_date, mood, stress_level, caffeine_after_17,
                   alcohol, screens_min_before_bed, notes
            FROM sleep_journal
            WHERE user_id = %s
            ORDER BY entry_date DESC
            LIMIT 1
            """,
            (user_id,),
        )
        journal = cur.fetchone()
        if journal:
            ctx["journal"] = {
                "entry_date": journal["entry_date"].isoformat(),
                "mood": journal["mood"],
                "stress_level": journal["stress_level"],
                "caffeine_after_17": journal["caffeine_after_17"],
                "alcohol": journal["alcohol"],
                "screens_min_before_bed": journal["screens_min_before_bed"],
                "notes": journal["notes"],
            }

    return ctx


def format_context_for_claude(ctx: dict[str, Any]) -> str:
    """Convierte el dict a texto markdown legible para inyectarlo al system prompt."""
    lines = []
    lines.append(f"## Contexto biométrico del usuario (últimas {ctx['window_hours']} h)")
    lines.append(f"Timestamp actual (UTC): {ctx['now']}")

    if ctx.get("user"):
        u = ctx["user"]
        lines.append(f"Usuario: {u.get('name', 'desconocido')} · cronotipo: {u.get('chronotype', 'n/a')}")
    lines.append("")

    # Biometrics
    bio = ctx.get("biometrics", {})
    if bio:
        lines.append("### Estadísticos por métrica")
        for metric, stats in bio.items():
            lines.append(
                f"- **{metric}**: n={stats['n_samples']}, "
                f"media={stats['avg']}, min={stats['min']}, max={stats['max']}"
            )
        lines.append("")

    # Sleep phases
    if ctx.get("sleep_phases"):
        lines.append("### Distribución de fases de sueño")
        for phase, info in sorted(ctx["sleep_phases"].items(), key=lambda x: -x[1]["pct"]):
            lines.append(f"- {phase}: {info['pct']}% ({info['n']} muestras)")
        lines.append("")

    # Alertas
    if ctx.get("recent_alerts"):
        lines.append("### Alertas detectadas (Spark Streaming)")
        for a in ctx["recent_alerts"]:
            lines.append(f"- [{a['severity']}] {a['title']}: {a['text']}")
        lines.append("")

    # Diario
    if ctx.get("journal"):
        j = ctx["journal"]
        lines.append("### Última entrada del diario")
        lines.append(f"- Fecha: {j['entry_date']}")
        lines.append(f"- Mood: {j['mood']}/10, estrés: {j['stress_level']}/10")
        lines.append(f"- Cafeína tarde: {j['caffeine_after_17']}, alcohol: {j['alcohol']}")
        if j.get("screens_min_before_bed") is not None:
            lines.append(f"- Pantallas antes de dormir: {j['screens_min_before_bed']} min")
        if j.get("notes"):
            lines.append(f"- Notas: {j['notes']}")

    return "\n".join(lines)
