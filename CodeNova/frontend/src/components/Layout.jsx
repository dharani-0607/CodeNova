import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { dateTime, PRIORITY_COLORS } from '../lib/format'
import { useLive } from '../lib/live'
import { currentSubscription, disablePush, enablePush, pushSupported } from '../lib/push'

const NAV = [
  { to: '/', label: 'Dashboard', icon: '◧', end: true },
  { to: '/cameras', label: 'Live cameras', icon: '◉', staff: true },
  { to: '/alerts', label: 'Alerts', icon: '⚠', staff: true },
  { to: '/map', label: 'Campus map', icon: '⌖' },
  { to: '/report', label: 'Report incident', icon: '✚' },
  { to: '/news', label: 'Campus news', icon: '✉' },
  { to: '/moderation', label: 'Moderation', icon: '⚖', staff: true },
  { to: '/admin', label: 'Admin', icon: '⚙', admin: true },
]

export default function Layout() {
  const { user, isStaff, isAdmin, signOut, config } = useAuth()
  const { connected, toasts, dismissToast, unread, setUnread } = useLive()
  const [menuOpen, setMenuOpen] = useState(false)
  const [bellOpen, setBellOpen] = useState(false)
  const navigate = useNavigate()

  return (
    <div className="app">
      <aside className={`sidebar ${menuOpen ? 'open' : ''}`}>
        <Link to="/" className="brand" onClick={() => setMenuOpen(false)}>
          <img src="/icon.svg" alt="" />
          <div>
            <div className="brand-title">Campus Command</div>
            <div className="brand-sub">Amrita Coimbatore</div>
          </div>
        </Link>
        <nav>
          {NAV.filter((n) => (!n.staff || isStaff) && (!n.admin || isAdmin)).map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} onClick={() => setMenuOpen(false)}>
              <span className="nav-icon">{n.icon}</span>{n.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div className="small"><strong>{user.name}</strong></div>
          <div className="muted small">{user.email}</div>
          <div className="muted small">Role: {user.role}</div>
          <button className="btn ghost small" onClick={() => { signOut(); navigate('/login') }}>Sign out</button>
        </div>
      </aside>
      {menuOpen && <div className="scrim" onClick={() => setMenuOpen(false)} />}

      <div className="main">
        <header className="topbar">
          <button className="btn ghost menu-btn" onClick={() => setMenuOpen(true)} aria-label="Menu">☰</button>
          <div className="topbar-title">{config?.app_name || 'Campus Command Center'}</div>
          <span className={`conn ${connected ? 'on' : 'off'}`} title={connected ? 'Live updates connected' : 'Reconnecting…'}>
            {connected ? '● Live' : '○ Offline'}
          </span>
          <PushToggle vapidKey={config?.vapid_public_key} />
          <button className="btn ghost bell" onClick={() => { setBellOpen((o) => !o); setUnread(0) }} aria-label="Notifications">
            🔔{unread > 0 && <span className="bell-count">{unread}</span>}
          </button>
          {bellOpen && <NotificationPanel onClose={() => setBellOpen(false)} />}
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>

      <div className="toasts">
        {toasts.map((t) => (
          <div key={t.id} className="toast" style={{ borderLeftColor: PRIORITY_COLORS[t.priority] || '#888' }}
            onClick={() => { if (t.link) navigate(t.link); dismissToast(t.id) }}>
            <strong>{t.title}</strong>
            {t.body && <div className="small">{t.body.split('\n')[0]}</div>}
          </div>
        ))}
      </div>
    </div>
  )
}

function PushToggle({ vapidKey }) {
  const [on, setOn] = useState(false)
  const [busy, setBusy] = useState(false)
  useEffect(() => { currentSubscription().then((s) => setOn(!!s)).catch(() => {}) }, [])
  if (!pushSupported()) return null
  const toggle = async () => {
    setBusy(true)
    try {
      if (on) { await disablePush(); setOn(false) } else { await enablePush(vapidKey); setOn(true) }
    } catch (e) { alert(e.message) } finally { setBusy(false) }
  }
  return (
    <button className="btn ghost small" disabled={busy} onClick={toggle} title="Browser push notifications">
      {on ? 'Push on' : 'Enable push'}
    </button>
  )
}

function NotificationPanel({ onClose }) {
  const [items, setItems] = useState(null)
  const navigate = useNavigate()
  useEffect(() => { api('/api/notifications?limit=30').then(setItems).catch(() => setItems([])) }, [])
  return (
    <div className="notif-panel" onMouseLeave={onClose}>
      <div className="notif-head">Notifications</div>
      {items === null && <div className="muted small pad">Loading…</div>}
      {items && items.length === 0 && <div className="muted small pad">Nothing yet</div>}
      {items && items.map((n) => (
        <button key={n.id} className="notif-item" style={{ borderLeftColor: PRIORITY_COLORS[n.priority] }}
          onClick={() => { navigate(n.kind === 'alert' ? `/alerts/${n.ref_id}` : '/news'); onClose() }}>
          <div className="small"><strong>{n.title}</strong></div>
          <div className="muted small">{dateTime(n.created_at)}</div>
        </button>
      ))}
    </div>
  )
}
