import { useEffect, useRef, useState } from 'react'

/**
 * Hook simple para WebSocket con auto-reconexión y mensajes.
 *
 *   const { status, messages, send } = useWebSocket(url)
 */
export function useWebSocket(url) {
  const [status, setStatus]     = useState('connecting')   // 'connecting'|'open'|'closed'
  const [messages, setMessages] = useState([])
  const wsRef = useRef(null)
  const reconnectTimeout = useRef(null)

  useEffect(() => {
    if (!url) return
    let cancelled = false

    function connect() {
      if (cancelled) return
      setStatus('connecting')
      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen    = () => setStatus('open')
      ws.onclose   = () => {
        setStatus('closed')
        // reintenta a los 3 segundos
        if (!cancelled) reconnectTimeout.current = setTimeout(connect, 3000)
      }
      ws.onerror   = () => setStatus('closed')
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data)
          setMessages((prev) => [...prev.slice(-99), { ...msg, _t: Date.now() }])
        } catch {
          /* ignore */
        }
      }
    }
    connect()

    // Heartbeat para mantener viva la conexión
    const heartbeat = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send('ping')
      }
    }, 25000)

    return () => {
      cancelled = true
      clearInterval(heartbeat)
      if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current)
      if (wsRef.current) wsRef.current.close()
    }
  }, [url])

  const send = (data) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(typeof data === 'string' ? data : JSON.stringify(data))
    }
  }

  return { status, messages, send }
}
