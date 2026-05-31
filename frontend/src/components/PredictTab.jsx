import { useState } from 'react'
import { AlertTriangle, Loader2, Sparkles } from 'lucide-react'
import { api } from '../services/api'

const DEFAULTS = {
  age: 30, gender: 'Male', sleep_duration: 7.0, physical_activity: 60,
  stress_level: 4, bmi_category: 'Normal', heart_rate: 70, systolic: 120,
  sleep_disorder: 'None',
}

const CATEGORY_COLORS = {
  Insuficiente: 'bg-red-50 text-red-700 border-red-200',
  Buena:        'bg-night-50 text-night-700 border-night-200',
  Excelente:    'bg-emerald-50 text-emerald-700 border-emerald-200',
}

export default function PredictTab() {
  const [form, setForm]       = useState(DEFAULTS)
  const [loading, setLoading] = useState(false)
  const [result, setResult]   = useState(null)
  const [error, setError]     = useState(null)

  const update = (k, v) => setForm((f) => ({ ...f, [k]: v }))
  const toNum  = (v) => (v === '' ? '' : Number(v))

  async function submit(e) {
    e.preventDefault()
    setLoading(true); setError(null)
    try {
      const r = await api.predict(form)
      setResult(r)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fade-in grid grid-cols-1 lg:grid-cols-2 gap-6">
      <form onSubmit={submit} className="card space-y-4">
        <h2 className="text-xl font-bold text-night-950">Predicción con modelo MLflow</h2>
        <p className="text-sm text-slate-500">Carga el modelo desde el registry y predice la calidad del sueño.</p>

        <div className="grid grid-cols-2 gap-3">
          <Field label="Edad">
            <input type="number" min="10" max="100" required value={form.age}
                   onChange={(e) => update('age', toNum(e.target.value))} className="input" />
          </Field>
          <Field label="Sexo">
            <select value={form.gender} onChange={(e) => update('gender', e.target.value)} className="input">
              <option value="Male">Hombre</option>
              <option value="Female">Mujer</option>
            </select>
          </Field>
          <Field label="Duración (h)">
            <input type="number" step="0.1" min="1" max="14" required value={form.sleep_duration}
                   onChange={(e) => update('sleep_duration', toNum(e.target.value))} className="input" />
          </Field>
          <Field label={`Estrés: ${form.stress_level}/10`}>
            <input type="range" min="1" max="10" value={form.stress_level}
                   onChange={(e) => update('stress_level', toNum(e.target.value))}
                   className="w-full accent-night-500" />
          </Field>
          <Field label="Actividad (min/día)">
            <input type="number" min="0" max="300" value={form.physical_activity}
                   onChange={(e) => update('physical_activity', toNum(e.target.value))} className="input" />
          </Field>
          <Field label="HR (bpm)">
            <input type="number" min="40" max="200" value={form.heart_rate}
                   onChange={(e) => update('heart_rate', toNum(e.target.value))} className="input" />
          </Field>
          <Field label="Sistólica (mmHg)">
            <input type="number" min="80" max="200" value={form.systolic}
                   onChange={(e) => update('systolic', toNum(e.target.value))} className="input" />
          </Field>
          <Field label="IMC">
            <select value={form.bmi_category} onChange={(e) => update('bmi_category', e.target.value)} className="input">
              <option value="Normal">Normal</option>
              <option value="Overweight">Sobrepeso</option>
              <option value="Obese">Obesidad</option>
            </select>
          </Field>
          <Field label="Trastorno del sueño">
            <select value={form.sleep_disorder} onChange={(e) => update('sleep_disorder', e.target.value)} className="input">
              <option value="None">Ninguno</option>
              <option value="Insomnia">Insomnio</option>
              <option value="Sleep Apnea">Apnea del sueño</option>
            </select>
          </Field>
        </div>

        {error && (
          <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm flex gap-2">
            <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <div><strong>Error:</strong> {error}</div>
          </div>
        )}

        <button type="submit" disabled={loading} className="btn-primary w-full">
          {loading ? <><Loader2 className="w-4 h-4 animate-spin" /> Calculando…</>
                   : <><Sparkles className="w-4 h-4" /> Predecir calidad</>}
        </button>
      </form>

      <div className="card">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-500 mb-4">
          Resultado
        </h3>
        {!result && (
          <div className="text-center py-12 text-slate-400">
            Pulsa "Predecir" para ver el resultado del modelo MLflow.
          </div>
        )}
        {result && (
          <div className="space-y-4">
            <div className="text-center py-4">
              <div className="text-6xl font-extrabold text-night-950">{result.score_100}</div>
              <div className="text-xs text-slate-400 mt-1">/ 100</div>
              <span className={`inline-block mt-3 px-3 py-1 rounded-full text-sm font-semibold border ${CATEGORY_COLORS[result.category] || ''}`}>
                {result.category}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <Stat label="Quality bruto" value={result.raw_value?.toFixed(2)} />
              <Stat label="Score 0–100"  value={result.score_100} />
            </div>
            <div className="p-3 rounded-lg bg-night-50 border border-night-100 text-xs text-night-800">
              <strong>Modelo:</strong> sklearn GradientBoostingRegressor, cargado desde MLflow Registry
              (<code>models:/suenoia-sleep/latest</code>).
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function Field({ label, children }) {
  return <div><label className="label">{label}</label>{children}</div>
}
function Stat({ label, value }) {
  return <div className="p-3 rounded-lg bg-slate-50 border border-slate-100">
    <div className="text-xs text-slate-500">{label}</div>
    <div className="text-lg font-bold text-night-900">{value}</div>
  </div>
}
