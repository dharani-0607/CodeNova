import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Empty, ErrorNote, PriorityBadge, StatusBadge } from '../components/ui'
import { api, mediaUrl } from '../lib/api'
import { dateTime, label, PRIORITIES, STATUSES } from '../lib/format'
import { useLiveEvent } from '../lib/live'

export default function Alerts() {
  const navigate = useNavigate()
  const [filters, setFilters] = useState({ status: 'pending_review,open,acknowledged', priority: '', event_type: '', source: '', hours: '' })
  const [types, setTypes] = useState([])
  const [alerts, setAlerts] = useState(null)
  const [error, setError] = useState(null)

  const load = useCallback(() => {
    const q = new URLSearchParams({ limit: '300' })
    Object.entries(filters).forEach(([k, v]) => v && q.set(k, v))
    api(`/api/alerts?${q}`).then(setAlerts).catch(setError)
  }, [filters])

  useEffect(() => { load() }, [load])
  useEffect(() => { api('/api/event-types').then(setTypes).catch(() => {}) }, [])
  useLiveEvent((type) => { if (type === 'alert' || type === 'alert_update') load() }, [load])

  const set = (k) => (e) => setFilters({ ...filters, [k]: e.target.value })

  return (
    <div className="page">
      <div className="page-head"><h2>Alerts</h2></div>
      <div className="filters card">
        <select value={filters.status} onChange={set('status')}>
          <option value="pending_review,open,acknowledged">Active</option>
          <option value="">All statuses</option>
          {STATUSES.map((s) => <option key={s} value={s}>{label(s)}</option>)}
        </select>
        <select value={filters.priority} onChange={set('priority')}>
          <option value="">All priorities</option>
          {PRIORITIES.map((p) => <option key={p} value={p}>{label(p)}</option>)}
        </select>
        <select value={filters.event_type} onChange={set('event_type')}>
          <option value="">All event types</option>
          {types.map((t) => <option key={t.key} value={t.key}>{t.label}</option>)}
        </select>
        <select value={filters.source} onChange={set('source')}>
          <option value="">All sources</option>
          <option value="camera">Cameras</option>
          <option value="report">User reports</option>
          <option value="manual">Manual</option>
        </select>
        <select value={filters.hours} onChange={set('hours')}>
          <option value="">Any time</option>
          <option value="1">Last hour</option>
          <option value="24">Last 24 hours</option>
          <option value="168">Last 7 days</option>
        </select>
      </div>
      <ErrorNote error={error} />
      {alerts && alerts.length === 0 && <Empty>No alerts match these filters.</Empty>}
      {alerts && alerts.length > 0 && (
        <div className="table-wrap card">
          <table className="table">
            <thead>
              <tr><th></th><th>Alert</th><th>Priority</th><th>Status</th><th>Where</th><th>When</th></tr>
            </thead>
            <tbody>
              {alerts.map((a) => (
                <tr key={a.id} onClick={() => navigate(`/alerts/${a.id}`)} className="clickable">
                  <td>{a.image_url ? <img className="alert-thumb" src={mediaUrl(a.image_url)} alt="" loading="lazy" /> : null}</td>
                  <td>
                    <strong>{a.title}</strong>
                    <div className="muted small">{a.description?.slice(0, 100)}</div>
                  </td>
                  <td><PriorityBadge priority={a.priority} /></td>
                  <td><StatusBadge status={a.status} />{a.broadcast && <span className="badge">Broadcast</span>}</td>
                  <td className="small">{a.location_name || a.camera_name || '—'}{a.source === 'report' ? ' (report)' : ''}</td>
                  <td className="small nowrap">{dateTime(a.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
