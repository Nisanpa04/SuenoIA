import { useEffect, useState } from 'react'
import { Bot, MessageSquare, Radio } from 'lucide-react'
import Header from './components/Header'
import PredictTab from './components/PredictTab'
import ChatTab from './components/ChatTab'
import LiveTab from './components/LiveTab'
import { api } from './services/api'

const TABS = [
  { id: 'predict', label: 'Predict', icon: Bot },
  { id: 'chat',    label: 'Chat IA', icon: MessageSquare },
  { id: 'live',    label: 'Live',    icon: Radio },
]

export default function App() {
  const [tab, setTab] = useState('predict')
  const [apiUp, setApiUp] = useState(null)

  useEffect(() => {
    api.health()
      .then((h) => setApiUp(h.status === 'ok'))
      .catch(() => setApiUp(false))
    // re-chequeo cada 30s
    const t = setInterval(() => {
      api.health().then((h) => setApiUp(h.status === 'ok')).catch(() => setApiUp(false))
    }, 30000)
    return () => clearInterval(t)
  }, [])

  return (
    <div className="min-h-screen flex flex-col">
      <Header apiUp={apiUp} />

      <main className="flex-1 max-w-6xl mx-auto px-4 py-6 w-full">
        {/* Tab bar */}
        <div className="flex gap-2 mb-6 flex-wrap">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`tab flex items-center gap-2 ${tab === id ? 'tab-active' : 'tab-inactive'}`}
            >
              <Icon className="w-4 h-4" /> {label}
            </button>
          ))}
        </div>

        {tab === 'predict' && <PredictTab />}
        {tab === 'chat'    && <ChatTab />}
        {tab === 'live'    && <LiveTab />}
      </main>

      <footer className="py-6 text-center text-xs text-slate-400 border-t border-night-100 mt-6">
        SueñoIA v2 · Plataforma IoT de salud del sueño · Proyecto IA + Big Data
      </footer>
    </div>
  )
}
