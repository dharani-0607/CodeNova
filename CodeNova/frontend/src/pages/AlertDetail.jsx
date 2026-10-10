import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { MapContainer, Marker, Polygon, TileLayer } from 'react-leaflet'
import { ErrorNote, PriorityBadge, StatusBadge } from '../components/ui'
import { api, mediaUrl } from '../lib/api'
import { useAuth } from '../lib/auth'
import { dateTime, label, PRIORITIES } from '../lib/format'
import { useLiveEvent } from '../lib/live'
import { pinIcon } from './mapIcons'

export default function AlertDetail() {
  const { id } = useParams()
  const { isStaff, config } = useAuth()
  const [alert, setAlert] = useState(null)
  const [error, setError] = useState(null)
  const [notes, setNotes] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api(`/api/alerts/${id}`).then((a) => { setAlert(a); setNotes(a.notes || '') }).catch(setError)
  }, [id])
  useLiveEvent((type, data) => { if (type === 'alert_update' && String(data.id) === id) setAlert(data) }, [id])

  const update = async (body) => {
    setBusy(true); setError(null)
    try { setAlert(await api(`/api/alerts/${id}`, { method: 'PATCH', body })) } catch (e) { setError(e) } finally { setBusy(false) }
  }
  const broadcast = async () => {
    if (!confirm('Send this alert to every campus user (dashboard, push, and email if critical)?')) return
    setBusy(true)
    try { setAlert(await api(`/api/alerts/${id}/broadcast`, { method: 'POST' })) } catch (e) { setError(e) } finally { setBusy(false) }
  }

  if (error && !alert) return <ErrorNote error={error} />
  if (!alert) return <div className="muted">Loading…</div>
  const hasPos = alert.lat != null && alert.lon != null

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <Link to={isStaff ? '/alerts' : '/'} className="small">← Back</Link>
          <h2>{alert.title}</h2>
          <div className="row gap">
            <PriorityBadge priority={alert.priority} /> <StatusBadge status={alert.status} />
            {alert.broadcast && <span className="badge">Broadcast to campus</span>}
            <span className="muted small">{label(alert.event_type)} · {label(alert.source)} · {dateTime(alert.created_at)}</span>
          </div>
        </div>
      </div>
      <ErrorNote error={error} />
      <div className="grid-2">
        <div className="stack">
          {alert.image_url && (
            <a href={mediaUrl(alert.image_url)} target="_blank" rel="noreferrer" className="card evidence">
              <img src={mediaUrl(alert.image_url)} alt="Evidence" />
            </a>
          )}
          <section className="card">
            <h3>Details</h3>
            <p className="pre">{alert.description || 'No description.'}</p>
            <dl className="dl">
              <dt>Location</dt><dd>{alert.location_name || alert.camera_name || '—'}</dd>
              {alert.confidence != null && (<><dt>Model confidence</dt><dd>{Math.round(alert.confidence * 100)}%</dd></>)}
              {alert.reporter && (<><dt>Reported by</dt><dd>{alert.reporter.name} ({alert.reporter.email})</dd></>)}
              {Object.entries(alert.extra || {}).filter(([, v]) => v != null && typeof v !== 'object').map(([k, v]) => (
                <span key={k} style={{ display: 'contents' }}><dt>{label(k)}</dt><dd>{String(v)}</dd></span>
              ))}
            </dl>
          </section>
        </div>
        <div className="stack">
          {isStaff && (
            <section className="card">
              <h3>Response</h3>
              {alert.status === 'pending_review' && (
                <div className="info-note">The model flagged this but it may be a false alarm. Check the snapshot and confirm or dismiss it.</div>
              )}
              <div className="row gap wrap">
                {alert.status === 'pending_review' && <button className="btn primary" disabled={busy} onClick={() => update({ status: 'open' })}>Confirm alert</button>}
                {['pending_review', 'open'].includes(alert.status) && <button className="btn" disabled={busy} onClick={() => update({ status: 'acknowledged' })}>Acknowledge</button>}
                {alert.status !== 'resolved' && <button className="btn success" disabled={busy} onClick={() => update({ status: 'resolved', notes })}>Resolve</button>}
                {alert.status !== 'dismissed' && <button className="btn ghost" disabled={busy} onClick={() => update({ status: 'dismissed', notes })}>Dismiss (false alarm)</button>}
                {!alert.broadcast && <button className="btn danger" disabled={busy} onClick={broadcast}>Broadcast to campus</button>}
              </div>
              <label className="form-row">Priority
                <select value={alert.priority} disabled={busy} onChange={(e) => update({ priority: e.target.value })}>
                  {PRIORITIES.map((p) => <option key={p} value={p}>{label(p)}</option>)}
                </select>
              </label>
              <label className="form-row">Notes
                <textarea rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Actions taken, team dispatched…" />
              </label>
              <button className="btn small" disabled={busy} onClick={() => update({ notes })}>Save notes</button>
            </section>
          )}
          {hasPos && (
            <section className="card map-card">
              <MapContainer center={[alert.lat, alert.lon]} zoom={17} style={{ height: 300 }}>
                <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="© OpenStreetMap" />
                {config?.geofence && <Polygon positions={config.geofence} pathOptions={{ color: '#a4123f', fillOpacity: 0.05 }} />}
                <Marker position={[alert.lat, alert.lon]} icon={pinIcon(alert.priority)} />
              </MapContainer>
            </section>
          )}
        </div>
      </div>
    </div>
  )
}
