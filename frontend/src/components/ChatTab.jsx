import { useEffect, useRef, useState } from 'react'
import { Bot, Loader2, Send, Sparkles, User } from 'lucide-react'
import { api } from '../services/api'

const QUICK_PROMPTS = [
  '¿Cómo está siendo mi sueño esta noche?',
  '¿Qué puedo mejorar de mi descanso?',
  '¿Cómo está mi HRV últimamente?',
  'Dame consejos para dormirme antes',
]

export default function ChatTab() {
  const [messages, setMessages] = useState([])
  const [input, setInput]       = useState('')
  const [loading, setLoading]   = useState(false)
  const [preset, setPreset]     = useState('default')
  const endRef = useRef(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  async function send(text) {
    const userMsg = { role: 'user', content: text }
    setMessages((m) => [...m, userMsg])
    setInput('')
    setLoading(true)
    try {
      const r = await api.chat({
        user_id: 1,
        message: text,
        history: messages,
        preset,
        include_context: true,
      })
      setMessages((m) => [...m, { role: 'assistant', content: r.text, usage: r.usage }])
    } catch (e) {
      setMessages((m) => [...m, { role: 'assistant', content: `❌ Error: ${e.message}` }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fade-in card flex flex-col h-[75vh]">
      <div className="flex items-center justify-between mb-3 border-b border-night-100 pb-3">
        <div>
          <h2 className="text-xl font-bold text-night-950 flex items-center gap-2">
            <Bot className="w-5 h-5 text-night-600" /> Coach de sueño con Claude
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Cada respuesta usa tus datos biométricos reales de las últimas 6 horas.
          </p>
        </div>
        <select value={preset} onChange={(e) => setPreset(e.target.value)} className="input max-w-[180px] text-sm">
          <option value="default">Modo: coach general</option>
          <option value="pre_sleep">Modo: pre-sueño</option>
          <option value="post_sleep">Modo: post-despertar</option>
        </select>
      </div>

      <div className="flex-1 overflow-y-auto space-y-3 pr-1">
        {messages.length === 0 && (
          <div className="text-center py-10">
            <Sparkles className="w-10 h-10 mx-auto text-night-300 mb-3" />
            <p className="text-sm text-slate-500 mb-4">Empieza con uno de estos:</p>
            <div className="flex flex-wrap justify-center gap-2 max-w-md mx-auto">
              {QUICK_PROMPTS.map((p, i) => (
                <button key={i} onClick={() => send(p)}
                        className="btn-ghost border border-night-200 hover:border-night-400">
                  {p}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <Message key={i} m={m} />
        ))}
        {loading && (
          <div className="flex items-center gap-2 text-sm text-slate-500 pl-12">
            <Loader2 className="w-4 h-4 animate-spin" /> Claude está pensando…
          </div>
        )}
        <div ref={endRef} />
      </div>

      <form
        onSubmit={(e) => { e.preventDefault(); if (input.trim() && !loading) send(input.trim()) }}
        className="mt-3 flex gap-2 border-t border-night-100 pt-3"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Pregúntale a tu coach…"
          className="input flex-1"
        />
        <button type="submit" disabled={loading || !input.trim()} className="btn-primary">
          <Send className="w-4 h-4" />
        </button>
      </form>
    </div>
  )
}

function Message({ m }) {
  const isUser = m.role === 'user'
  return (
    <div className={`flex gap-3 fade-in ${isUser ? 'flex-row-reverse' : ''}`}>
      <div className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0
        ${isUser ? 'bg-night-100 text-night-700' : 'bg-gradient-to-br from-night-600 to-night-400 text-white'}`}>
        {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
      </div>
      <div className={`flex-1 p-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap
        ${isUser ? 'bg-night-50 text-night-900' : 'bg-white border border-night-100 text-slate-800'}`}>
        {m.content}
        {m.usage && (
          <div className="mt-2 text-xs text-slate-400">
            🪙 {m.usage.input_tokens} in / {m.usage.output_tokens} out
          </div>
        )}
      </div>
    </div>
  )
}
