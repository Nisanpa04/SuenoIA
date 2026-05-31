import { Moon, Wifi, WifiOff } from 'lucide-react'

export default function Header({ apiUp }) {
  return (
    <header className="sticky top-0 z-20 backdrop-blur-md bg-white/70 border-b border-night-100">
      <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-night-600 to-night-400
                          flex items-center justify-center shadow-soft">
            <Moon className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-night-900 leading-none">SueñoIA v2</h1>
            <p className="text-xs text-slate-500 mt-0.5">Plataforma IoT de salud del sueño</p>
          </div>
        </div>
        <ApiStatus up={apiUp} />
      </div>
    </header>
  )
}

function ApiStatus({ up }) {
  if (up === null)
    return <span className="chip border-slate-200 text-slate-400">
      <span className="w-2 h-2 rounded-full bg-slate-300 pulse-dot" /> Comprobando
    </span>
  if (up)
    return <span className="chip border-emerald-200 bg-emerald-50 text-emerald-700">
      <Wifi className="w-3.5 h-3.5" /> Backend conectado
    </span>
  return <span className="chip border-red-200 bg-red-50 text-red-700">
    <WifiOff className="w-3.5 h-3.5" /> Backend offline
  </span>
}
