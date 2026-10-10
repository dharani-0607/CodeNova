import { useEffect, useState } from 'react'
import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import { MapContainer, Polygon, TileLayer, useMapEvents, CircleMarker } from 'react-leaflet'
import { ErrorNote } from '../components/ui'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { dateTime, label, PRIORITIES } from '../lib/format'
import CameraAdmin from './CameraAdmin'

export default function Admin() {
  const tabs = [
    ['cameras', 'Cameras'], ['events', 'Event priorities'], ['geofence', 'Geofence'],
    ['campus', 'Campus settings'], ['moderation', 'Moderation rules'], ['users', 'Users'],
  ]
  return (
    <div className="page">
      <div className="page-head"><h2>Administration</h2></div>
      <div className="tabs underline">
        {tabs.map(([to, l]) => <NavLink key={to} to={`/admin/${to}`}>{l}</NavLink>)}
      </div>
      <Routes>
        <Route index element={<Navigate to="cameras" replace />} />
        <Route path="cameras" element={<CameraAdmin />} />
        <Route path="events" element={<EventTypes />} />
        <Route path="geofence" element={<Geofence />} />
        <Route path="campus" element={<CampusSettings />} />
        <Route path="moderation" element={<ModerationRules />} />
        <Route path="users" element={<Users />} />
      </Routes>
    </div>
  )
}

function EventTypes() {
  const [types, setTypes] = useState([])
  const [error, setError] = useState(null)
  useEffect(() => { api('/api/event-types').then(setTypes).catch(setError) }, [])
  const update = async (key, patch) => {
    try {
      const t = await api(`/api/event-types/${key}`, { method: 'PATCH', body: patch })
      setTypes((ts) => ts.map((x) => (x.key === key ? t : x)))
    } catch (e) { setError(e) }
  }
  const group = (cat) => types.filter((t) => t.category === cat)
  return (
    <div className="stack">
      <p className="muted">Set the priority and handling of each kind of event. Security can still change the priority of any single alert.</p>
      <ErrorNote error={error} />
      {['camera', 'report'].map((cat) => (
        <div key={cat} className="table-wrap card">
          <h3>{cat === 'camera' ? 'Camera detections' : 'User reports'}</h3>
          <table className="table">
            <thead><tr>
              <th>Event</th><th>Priority</th><th title="Wait for security to confirm before notifying">Needs review</th>
              <th title="Announce confirmed alerts to every campus user">Broadcast to all</th><th>Email (critical/high)</th>
              <th>Push</th><th title="Ignore repeats on the same camera/zone within this many seconds">Cooldown (s)</th><th>Enabled</th>
            </tr></thead>
            <tbody>
              {group(cat).map((t) => (
                <tr key={t.key}>
                  <td><strong>{t.label}</strong><div className="muted small mono">{t.key}</div></td>
                  <td>
                    <select value={t.default_priority} onChange={(e) => update(t.key, { default_priority: e.target.value })} className={`prio-select prio-${t.default_priority}`}>
                      {PRIORITIES.map((p) => <option key={p} value={p}>{label(p)}</option>)}
                    </select>
                  </td>
                  {['requires_review', 'public_broadcast', 'notify_email', 'notify_push'].map((f) => (
                    <td key={f}><input type="checkbox" checked={t[f]} onChange={(e) => update(t.key, { [f]: e.target.checked })} /></td>
                  ))}
                  <td><input type="number" min="0" className="num" defaultValue={t.cooldown_seconds}
                    onBlur={(e) => Number(e.target.value) !== t.cooldown_seconds && update(t.key, { cooldown_seconds: Number(e.target.value) })} /></td>
                  <td><input type="checkbox" checked={t.enabled} onChange={(e) => update(t.key, { enabled: e.target.checked })} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  )
}

function Geofence() {
  const { config, refreshConfig } = useAuth()
  const [points, setPoints] = useState(config?.geofence || [])
  const [error, setError] = useState(null)
  const [saved, setSaved] = useState(false)
  if (!config) return null
  const save = async () => {
    setError(null)
    try {
      const lat = points.reduce((s, p) => s + p[0], 0) / points.length
      const lon = points.reduce((s, p) => s + p[1], 0) / points.length
      await api('/api/geofence', { method: 'PUT', body: { polygon: points, center: [lat, lon] } })
      await refreshConfig(); setSaved(true); setTimeout(() => setSaved(false), 2500)
    } catch (e) { setError(e) }
  }
  return (
    <div className="stack">
      <p className="muted">Click on the map to trace the campus boundary point by point. Reports from outside this polygon are refused. The default is only a rough box, so trace the real boundary before going live.</p>
      <div className="card map-card">
        <MapContainer center={config.campus_center} zoom={15} style={{ height: 480 }}>
          <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="© OpenStreetMap" />
          <AddPoint onAdd={(p) => setPoints((ps) => [...ps, p])} />
          {points.length > 1 && <Polygon positions={points} pathOptions={{ color: '#a4123f', fillOpacity: 0.08 }} />}
          {points.map((p, i) => <CircleMarker key={i} center={p} radius={4} pathOptions={{ color: '#a4123f' }} />)}
        </MapContainer>
      </div>
      <div className="row gap wrap">
        <button className="btn primary" disabled={points.length < 3} onClick={save}>Save geofence ({points.length} points)</button>
        <button className="btn" onClick={() => setPoints((p) => p.slice(0, -1))} disabled={!points.length}>Undo last point</button>
        <button className="btn ghost" onClick={() => setPoints([])}>Start over</button>
        <button className="btn ghost" onClick={() => setPoints(config.geofence)}>Reset to saved</button>
        {saved && <span className="info-note">Saved</span>}
      </div>
      <ErrorNote error={error} />
    </div>
  )
}

function AddPoint({ onAdd }) {
  useMapEvents({ click: (e) => onAdd([+e.latlng.lat.toFixed(6), +e.latlng.lng.toFixed(6)]) })
  return null
}

function CampusSettings() {
  const [s, setS] = useState(null)
  const [error, setError] = useState(null)
  const [saved, setSaved] = useState(false)
  useEffect(() => { api('/api/settings/campus').then(setS).catch(setError) }, [])
  if (!s) return <ErrorNote error={error} />
  const save = async (e) => {
    e.preventDefault()
    try {
      setS(await api('/api/settings/campus', { method: 'PUT', body: { ...s, speed_limit_kmh: Number(s.speed_limit_kmh), max_gps_accuracy_m: Number(s.max_gps_accuracy_m) } }))
      setSaved(true); setTimeout(() => setSaved(false), 2500); setError(null)
    } catch (err) { setError(err) }
  }
  return (
    <form className="card form narrow" onSubmit={save}>
      <label>Campus speed limit (km/h)<input type="number" min="5" max="120" value={s.speed_limit_kmh} onChange={(e) => setS({ ...s, speed_limit_kmh: e.target.value })} /></label>
      <div className="row gap">
        <label className="grow">After hours from<input type="time" value={s.after_hours.from} onChange={(e) => setS({ ...s, after_hours: { ...s.after_hours, from: e.target.value } })} /></label>
        <label className="grow">until<input type="time" value={s.after_hours.to} onChange={(e) => setS({ ...s, after_hours: { ...s.after_hours, to: e.target.value } })} /></label>
      </div>
      <label>Max GPS error for reports (metres)<input type="number" min="10" value={s.max_gps_accuracy_m} onChange={(e) => setS({ ...s, max_gps_accuracy_m: e.target.value })} /></label>
      <ErrorNote error={error} />
      <div className="row gap"><button className="btn primary">Save</button>{saved && <span className="info-note">Saved</span>}<PushTest /></div>
    </form>
  )
}

function PushTest() {
  const [msg, setMsg] = useState(null)
  return (
    <>
      <button type="button" className="btn ghost small" onClick={() => api('/api/notifications/push/test', { method: 'POST' }).then(() => setMsg('Test push sent to your subscribed browsers')).catch((e) => setMsg(e.message))}>Send test push</button>
      {msg && <span className="small muted">{msg}</span>}
    </>
  )
}

function ModerationRules() {
  const [m, setM] = useState(null)
  const [error, setError] = useState(null)
  const [saved, setSaved] = useState(false)
  useEffect(() => {
    api('/api/settings/moderation').then((d) => setM({ ...d, banned: d.banned_terms.join('\n'), review: d.review_terms.join('\n') })).catch(setError)
  }, [])
  if (!m) return <ErrorNote error={error} />
  const save = async (e) => {
    e.preventDefault()
    try {
      const d = await api('/api/settings/moderation', { method: 'PUT', body: {
        flag_threshold: Number(m.flag_threshold), remove_threshold: Number(m.remove_threshold),
        banned_terms: m.banned.split('\n'), review_terms: m.review.split('\n'),
      } })
      setM({ ...d, banned: d.banned_terms.join('\n'), review: d.review_terms.join('\n') })
      setSaved(true); setTimeout(() => setSaved(false), 2500); setError(null)
    } catch (err) { setError(err) }
  }
  return (
    <form className="card form" onSubmit={save}>
      <div className="info-note small">
        AI model: <strong>{m.model.model}</strong> – {m.model.loaded ? 'loaded' : m.model.enabled ? (m.model.error ? `not available (${m.model.error})` : 'loads on first post') : 'disabled'}.
        Campus rule lists below always apply.
      </div>
      <div className="row gap">
        <label className="grow">Hold for review when toxicity ≥<input type="number" step="0.05" min="0.05" max="1" value={m.flag_threshold} onChange={(e) => setM({ ...m, flag_threshold: e.target.value })} /></label>
        <label className="grow">Remove automatically when ≥<input type="number" step="0.05" min="0.05" max="1" value={m.remove_threshold} onChange={(e) => setM({ ...m, remove_threshold: e.target.value })} /></label>
      </div>
      <div className="grid-2">
        <label>Banned terms – posts are removed (one per line)<textarea rows={10} value={m.banned} onChange={(e) => setM({ ...m, banned: e.target.value })} /></label>
        <label>Sensitive terms – held for admin review (one per line)<textarea rows={10} value={m.review} onChange={(e) => setM({ ...m, review: e.target.value })} /></label>
      </div>
      <ErrorNote error={error} />
      <div className="row gap"><button className="btn primary">Save rules</button>{saved && <span className="info-note">Saved</span>}</div>
    </form>
  )
}

function Users() {
  const { user: me } = useAuth()
  const [users, setUsers] = useState([])
  const [q, setQ] = useState('')
  const [error, setError] = useState(null)
  useEffect(() => { api('/api/users').then(setUsers).catch(setError) }, [])
  const update = async (id, patch) => {
    try {
      const u = await api(`/api/users/${id}`, { method: 'PATCH', body: patch })
      setUsers((us) => us.map((x) => (x.id === id ? u : x)))
    } catch (e) { setError(e) }
  }
  const shown = users.filter((u) => !q || (u.email + u.name).toLowerCase().includes(q.toLowerCase()))
  return (
    <div className="stack">
      <input placeholder="Search users" value={q} onChange={(e) => setQ(e.target.value)} className="narrow" />
      <ErrorNote error={error} />
      <div className="table-wrap card">
        <table className="table">
          <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Verified</th><th>Active</th><th>Joined</th></tr></thead>
          <tbody>
            {shown.map((u) => (
              <tr key={u.id}>
                <td>{u.name}</td>
                <td className="small">{u.email}</td>
                <td>
                  <select value={u.role} disabled={u.id === me.id} onChange={(e) => update(u.id, { role: e.target.value })}>
                    <option value="user">User</option><option value="security">Security</option><option value="admin">Admin</option>
                  </select>
                </td>
                <td>{u.is_verified ? '✓' : '—'}</td>
                <td><input type="checkbox" checked={u.is_active} disabled={u.id === me.id} onChange={(e) => update(u.id, { is_active: e.target.checked })} /></td>
                <td className="small">{dateTime(u.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
