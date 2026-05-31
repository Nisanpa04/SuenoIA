import { useEffect, useState } from 'react'
import {
  Activity, AlertTriangle, Bell, BellOff, Heart, RefreshCw,
  Thermometer, Wind, Zap,
} from 'lucide-react'
import { api, HTTP_URL, WS_URL } from '../services/api'
import { useWebSocket } from '../hooks/useWebSocket'

const SEVERITY = {
  critical: { color: 'bg-red-500',   chip: 'bg-red-50 text-red-700 border-red-200' },
  warning:  { color: 'bg-amber-500', chip: 'bg-amber-50 text-amber-700 border-amber-200' },
  info:     { color: 'bg-night-500', chip: 'bg-night-50 text-night-700 border-night-200' },
}

export default function LiveTab() {
  const userId = 1
  const wsUrl  = `${WS_URL}/ws/alerts/${userId}`
  const { status, messages } = useWebSocket(wsUrl)
  const [ctx, setCtx]               = useState(null)
  const [ctxError, setCtxError]     = useState(null)
  const [loadingCtx, setLoadingCtx] = useState(false)
  const [lastUpdate, setLastUpdate] = useState(null)
  const [testFeedback, setTestFeedback] = useState(null)

  async function refreshCtx() {
    setLoadingCtx(true); setCtxError(null)
    try {
      const r = await api.context(userId, 6)
      setCtx(r)
      setLastUpdate(new Date())
    } catch (e) {
      setCtxError(e.message)
      setCtx(null)
    } finally { setLoadingCtx(false) }
  }
  useEffect(() => {
    refreshCtx()
    const t = setInterval(refreshCtx, 10000)
    return () => clearInterval(t)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function injectTestAlert(severity) {
    setTestFeedback({ loading: true, severity })
    try {
      await api.testAlert(userId, severity)
      setTestFeedback({ ok: true, severity, ts: Date.now() })
      setTimeout(() => setTestFeedback(null), 3500)
    } catch (e) {
      setTestFeedback({ ok: false, error: e.message, ts: Date.now() })
    }
  }

  const alerts = messages
    .filter((m) => m.type === 'alert')
    .map((m) => m.data)
    .reverse()

  const wsBadge =
    status === 'open'
      ? <span className="chip bg-emerald-50 text-emerald-700 border-emerald-200">
          <Bell className="w-3.5 h-3.5" /> conectado
        </span>
      : status === 'connecting'
        ? <span className="chip bg-amber-50 text-amber-700 border-amber-200">
            <span className="w-2 h-2 rounded-full bg-amber-500 pulse-dot" /> conectando…
          </span>
        : <span className="chip bg-red-50 text-red-700 border-red-200">
            <BellOff className="w-3.5 h-3.5" /> desconectado
          </span>

  return (
    <div className="fade-in space-y-6">
      {/* Header + diagnostico */}
      <div className="card">
        <div className="flex items-start justify-between flex-wrap gap-3">
          <div>
            <h2 className="text-xl font-bold text-night-950">📡 Monitor en vivo</h2>
            <p className="text-xs text-slate-500 mt-1">
              <code>{HTTP_URL}</code> · WS: <code>{wsUrl}</code>
            </p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {wsBadge}
            <span className="chip border-night-200 text-night-700">
              {alerts.length} alertas
            </span>
            <button onClick={refreshCtx} disabled={loadingCtx} className="btn-ghost border border-night-200">
              <RefreshCw className={`w-4 h-4 ${loadingCtx ? 'animate-spin' : ''}`} />
              {lastUpdate ? `actualizado ${lastUpdate.toLocaleTimeString()}` : 'refrescar'}
            </button>
          </div>
        </div>

        {/* Botones de test */}
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <span className="text-xs text-slate-500 mr-2">🧪 Inyectar alerta de test:</span>
          {['info', 'warning', 'critical'].map((sev) => (
            <button key={sev} onClick={() => injectTestAlert(sev)}
                    className={`chip cursor-pointer hover:opacity-80 ${SEVERITY[sev].chip}`}>
              <Zap className="w-3 h-3" /> {sev}
            </button>
          ))}
          {testFeedback?.ok && (
            <span className="text-xs text-emerald-700">
              ✓ alerta {testFeedback.severity} enviada (debería llegar abajo)
            </span>
          )}
          {testFeedback?.ok === false && (
            <span className="text-xs text-red-700">✗ {testFeedback.error}</span>
          )}
        </div>

        {ctxError && (
          <div className="mt-3 p-3 rounded-lg bg-red-50 border border-red-200 text-sm">
            <strong className="text-red-800">No se pudo cargar el contexto:</strong>{' '}
            <span className="text-red-700">{ctxError}</span>
            <div className="text-xs text-red-600 mt-1">
              Verifica que el backend está corriendo en <code>{HTTP_URL}</code>.
            </div>
          </div>
        )}
      </div>

      {/* Tarjetas biométricas */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <BioCard icon={<Heart />}       label="HR media"   stats={ctx?.biometrics?.heart_rate}  unit="bpm" />
        <BioCard icon={<Activity />}    label="HRV media"  stats={ctx?.biometrics?.hrv}         unit="ms"  />
        <BioCard icon={<Wind />}        label="SpO₂ media" stats={ctx?.biometrics?.oxygen}      unit="%"   />
        <BioCard icon={<Thermometer />} label="Temp media" stats={ctx?.biometrics?.temperature} unit="°C"  />
      </div>

      {/* Fases + alertas */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-500 mb-3">
            Fases de sueño (últimas 6 h)
          </h3>
          {ctx?.sleep_phases && Object.keys(ctx.sleep_phases).length > 0 ? (
            <div className="space-y-2">
              {Object.entries(ctx.sleep_phases)
                .sort(([, a], [, b]) => b.pct - a.pct)
                .map(([phase, info]) => (
                  <div key={phase}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="font-medium text-slate-700">{phase}</span>
                      <span className="text-slate-500">{info.pct}% · {info.n}</span>
                    </div>
                    <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                      <div className="h-full bg-gradient-to-r from-night-500 to-night-300"
                           style={{ width: `${info.pct}%` }} />
                    </div>
                  </div>
                ))}
            </div>
          ) : (
            <p className="text-sm text-slate-400 py-8 text-center">
              Sin datos aún. Asegúrate de que el simulador está corriendo.
            </p>
          )}
        </div>

        <div className="card">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-500 mb-3">
            🔔 Stream de alertas (WebSocket)
          </h3>
          {alerts.length === 0 ? (
            <div className="py-8 text-center">
              <p className="text-sm text-slate-400 mb-2">Esperando alertas…</p>
              <p className="text-xs text-slate-400">
                Pulsa un botón "Inyectar alerta de test" arriba para probar el pipeline.
              </p>
            </div>
          ) : (
            <ul className="space-y-2 max-h-[24rem] overflow-y-auto">
              {alerts.map((a, i) => {
                const sev = SEVERITY[a.severity] || SEVERITY.info
                return (
                  <li key={i} className="flex gap-3 p-3 rounded-lg bg-slate-50 border border-slate-100 fade-in">
                    <div className={`w-9 h-9 rounded-lg ${sev.color} flex items-center justify-center flex-shrink-0`}>
                      <AlertTriangle className="w-4 h-4 text-white" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        <span className={`chip ${sev.chip}`}>{a.severity}</span>
                        <span className="text-xs text-slate-400">{a.category}</span>
                      </div>
                      <div className="font-medium text-sm text-slate-800">{a.title}</div>
                      <div className="text-xs text-slate-500 mt-0.5">{a.text}</div>
                    </div>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </div>

      <div className="card bg-gradient-to-r from-night-50 to-fuchsia-50 border border-night-200">
        <p className="text-sm">
          ¿Quieres más métricas e histórico? Abre{' '}
          <a href="http://localhost:3001/d/suenoia-live" target="_blank" rel="noreferrer"
             className="text-night-700 font-semibold underline hover:text-night-900">
            Grafana — Live Monitoring →
          </a>
        </p>
      </div>
    </div>
  )
}

function BioCard({ icon, label, stats, unit }) {
  return (
    <div className="card">
      <div className="flex items-center justify-between mb-2">
        <div className="w-9 h-9 rounded-lg bg-night-100 text-night-700 flex items-center justify-center">
          {icon}
        </div>
        <span className="text-xs text-slate-400">{stats?.n_samples ?? 0} muestras</span>
      </div>
      <div className="text-xs text-slate-500 uppercase tracking-wider">{label}</div>
      <div className="mt-1 flex items-baseline gap-1">
        <span className="text-2xl font-bold text-night-950 tabular-nums">
          {stats?.avg ?? '–'}
        </span>
        {stats?.avg !== undefined && stats?.avg !== null && (
          <span className="text-xs text-slate-400">{unit}</span>
        )}
      </div>
      {stats && (
        <div className="mt-1 text-xs text-slate-400 tabular-nums">
          min {stats.min} · max {stats.max}
        </div>
      )}
    </div>
  )
}
