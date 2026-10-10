// Thin fetch wrapper for the FastAPI backend.
const BASE = import.meta.env.VITE_API_URL || ''
const TOKEN_KEY = 'campus_token'

export function getToken() {
  try { return localStorage.getItem(TOKEN_KEY) } catch { return null }
}

export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch { /* storage blocked: session-only login */ }
}

export class ApiError extends Error {
  constructor(status, message) {
    super(message)
    this.status = status
  }
}

export async function api(path, { method = 'GET', body, form, headers = {} } = {}) {
  const token = getToken()
  const opts = { method, headers: { ...headers } }
  if (token) opts.headers.Authorization = `Bearer ${token}`
  if (form) {
    opts.body = form
  } else if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json'
    opts.body = JSON.stringify(body)
  }
  const res = await fetch(BASE + path, opts)
  let data = null
  const text = await res.text()
  try { data = text ? JSON.parse(text) : null } catch { data = text }
  if (!res.ok) {
    let msg = (data && data.detail) || res.statusText
    if (Array.isArray(msg)) msg = msg.map((d) => `${(d.loc || []).slice(-1)[0]}: ${d.msg}`).join(', ')
    if (res.status === 401 && token) {
      setToken(null)
      window.dispatchEvent(new Event('campus-logout'))
    }
    throw new ApiError(res.status, msg)
  }
  return data
}

// Media files need the token as a query parameter because <img> cannot send headers.
export function mediaUrl(path) {
  if (!path) return null
  return `${BASE}${path}?token=${encodeURIComponent(getToken() || '')}`
}

export function wsUrl() {
  const base = BASE || window.location.origin
  return base.replace(/^http/, 'ws') + `/ws?token=${encodeURIComponent(getToken() || '')}`
}

export function videoUrl(videoBase, kind, cameraId) {
  return `${videoBase}/${kind}/${cameraId}?token=${encodeURIComponent(getToken() || '')}`
}
