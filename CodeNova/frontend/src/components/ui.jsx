import { Link } from 'react-router-dom'
import { mediaUrl, videoUrl } from '../lib/api'
import { label, PRIORITY_COLORS, timeAgo } from '../lib/format'
import { useLive } from '../lib/live'

export function PriorityBadge({ priority }) {
  return <span className={`badge prio-${priority}`}>{label(priority)}</span>
}

export function StatusBadge({ status }) {
  return <span className={`badge status-${status}`}>{label(status)}</span>
}

export function Empty({ children }) {
  return <div className="empty">{children}</div>
}

export function ErrorNote({ error }) {
  if (!error) return null
  return <div className="error-note">{String(error.message || error)}</div>
}

export function Stat({ label: l, value, tone }) {
  return (
    <div className={`stat ${tone ? 'tone-' + tone : ''}`}>
      <div className="stat-value">{value ?? '–'}</div>
      <div className="stat-label">{l}</div>
    </div>
  )
}

export function AlertRow({ alert, compact }) {
  return (
    <Link to={`/alerts/${alert.id}`} className="alert-row" style={{ borderLeftColor: PRIORITY_COLORS[alert.priority] }}>
      {!compact && alert.image_url && <img src={mediaUrl(alert.image_url)} alt="" className="alert-thumb" loading="lazy" />}
      <div className="alert-row-main">
        <div className="alert-row-title">{alert.title}</div>
        <div className="muted small">
          {alert.location_name || alert.camera_name || 'Campus'} · {timeAgo(alert.created_at)}
          {alert.source === 'report' && ' · user report'}
        </div>
      </div>
      <div className="alert-row-badges">
        <PriorityBadge priority={alert.priority} />
        {!compact && <StatusBadge status={alert.status} />}
      </div>
    </Link>
  )
}

export function CameraTile({ camera, videoBase, large }) {
  const { cameraStats } = useLive()
  const stats = cameraStats[camera.id] || camera.status || {}
  return (
    <div className={`camera-tile ${large ? 'large' : ''}`}>
      <div className="camera-video">
        {camera.enabled ? (
          <img src={videoUrl(videoBase, 'stream', camera.id)} alt={camera.name}
            onError={(e) => { e.currentTarget.style.visibility = 'hidden' }}
            onLoad={(e) => { e.currentTarget.style.visibility = 'visible' }} />
        ) : <div className="camera-off">Disabled</div>}
        <span className={`live-dot ${stats.online ? 'on' : 'off'}`}>{stats.online ? 'LIVE' : 'OFFLINE'}</span>
      </div>
      <div className="camera-meta">
        <div>
          <strong>{camera.name}</strong>
          <div className="muted small">{camera.location_name}</div>
        </div>
        <div className="camera-counts small">
          <span title="People in view">👥 {stats.people ?? 0}</span>
          <span title="Vehicles in view">🚗 {stats.vehicles ?? 0}</span>
          <span title="Frames analysed per second">{stats.fps ?? 0} fps</span>
        </div>
      </div>
      {stats.error && <div className="error-note small">{stats.error}</div>}
    </div>
  )
}

export function Modal({ title, onClose, children, wide }) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className={`modal ${wide ? 'wide' : ''}`} onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h3>{title}</h3>
          <button className="btn ghost" onClick={onClose} aria-label="Close">✕</button>
        </div>
        {children}
      </div>
    </div>
  )
}
