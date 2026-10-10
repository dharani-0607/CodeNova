// Live updates over WebSocket: alerts, campus alerts, news, camera stats, toasts.
import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { wsUrl } from './api'
import { useAuth } from './auth'

const LiveCtx = createContext(null)

export function LiveProvider({ children }) {
  const { user } = useAuth()
  const [connected, setConnected] = useState(false)
  const [toasts, setToasts] = useState([])
  const [cameraStats, setCameraStats] = useState({})
  const [unread, setUnread] = useState(0)
  const listeners = useRef(new Set())

  const pushToast = useCallback((toast) => {
    const id = Math.random().toString(36).slice(2)
    setToasts((t) => [...t.slice(-4), { id, ...toast }])
    const ttl = toast.priority === 'critical' ? 20000 : 8000
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), ttl)
  }, [])

  const dismissToast = (id) => setToasts((t) => t.filter((x) => x.id !== id))

  // Components subscribe with a callback(type, data)
  const subscribe = useCallback((fn) => {
    listeners.current.add(fn)
    return () => listeners.current.delete(fn)
  }, [])

  useEffect(() => {
    if (!user) return
    let ws, timer, ping, closed = false
    const connect = () => {
      ws = new WebSocket(wsUrl())
      ws.onopen = () => {
        setConnected(true)
        ping = setInterval(() => ws.readyState === 1 && ws.send('ping'), 25000)
      }
      ws.onclose = () => {
        setConnected(false)
        clearInterval(ping)
        if (!closed) timer = setTimeout(connect, 3000)
      }
      ws.onmessage = (ev) => {
        let msg
        try { msg = JSON.parse(ev.data) } catch { return }
        const { type, data } = msg
        if (type === 'camera_stats') setCameraStats(data)
        if (type === 'notification') {
          setUnread((n) => n + 1)
          pushToast({ title: data.title, body: data.body, priority: data.priority, link: data.kind === 'alert' ? `/alerts/${data.ref_id}` : '/news' })
          if (data.priority === 'critical') beep()
        }
        listeners.current.forEach((fn) => fn(type, data))
      }
    }
    connect()
    return () => { closed = true; clearTimeout(timer); clearInterval(ping); ws && ws.close() }
  }, [user, pushToast])

  return (
    <LiveCtx.Provider value={{ connected, toasts, dismissToast, pushToast, cameraStats, subscribe, unread, setUnread }}>
      {children}
    </LiveCtx.Provider>
  )
}

function beep() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)()
    const o = ctx.createOscillator()
    const g = ctx.createGain()
    o.frequency.value = 880
    o.connect(g); g.connect(ctx.destination)
    g.gain.setValueAtTime(0.2, ctx.currentTime)
    o.start(); o.stop(ctx.currentTime + 0.4)
  } catch { /* audio not allowed */ }
}

export const useLive = () => useContext(LiveCtx)

// Re-run `fn(type, data)` for live messages while mounted.
export function useLiveEvent(fn, deps = []) {
  const { subscribe } = useLive()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => subscribe(fn), [subscribe, ...deps])
}
