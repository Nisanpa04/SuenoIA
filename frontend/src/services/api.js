/** Cliente HTTP del backend v2. */

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
export const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000'
export const HTTP_URL = API_URL  // expuesto para mostrar en UI

async function request(path, opts = {}) {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      detail = body.detail || JSON.stringify(body)
    } catch {}
    throw new Error(detail)
  }
  return res.json()
}

export const api = {
  health:    () => request('/health'),
  predict:   (payload) => request('/predict', { method: 'POST', body: JSON.stringify(payload) }),
  chat:      (payload) => request('/chat',    { method: 'POST', body: JSON.stringify(payload) }),
  context:   (userId, hoursBack=6) => request(`/chat/context/${userId}?hours_back=${hoursBack}`),
  alerts:    (userId) => request(`/alerts/${userId}`),
  testAlert: (userId=1, severity='warning') =>
    request(`/test/alert?user_id=${userId}&severity=${severity}`, { method: 'POST' }),
  pipelineStatus: () => request('/test/pipeline-status'),
}
