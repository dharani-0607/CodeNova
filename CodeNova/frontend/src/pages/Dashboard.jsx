import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertRow, CameraTile, Empty, Stat } from '../components/ui'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { label, PRIORITY_COLORS, timeAgo } from '../lib/format'
import { useLiveEvent } from '../lib/live'

export default function Dashboard() {
  const { isStaff } = useAuth()
  return isStaff ? <StaffDashboard /> : <UserDashboard />
}

function StaffDashboard() {
  const { config } = useAuth()
  const [stats, setStats] = useState(null)
  const [alerts, setAlerts] = useState([])
  const [cameras, setCameras] = useState([])
  const [news, setNews] = useState([])

  const load = useCallback(() => {
    api('/api/alerts/stats?hours=24').then(setStats).catch(() => {})
    api('/api/alerts?active=true&limit=30').then(setAlerts).catch(() => {})
  }, [])

  useEffect(() => {
    load()
    api('/api/cameras').then(setCameras).catch(() => {})
    api('/api/news?limit=5').then(setNews).catch(() => {})
  }, [load])

  useLiveEvent((type, data) => {
    if (type === 'alert') setAlerts((a) => [data, ...a.filter((x) => x.id !== data.id)].slice(0, 30))
    if (type === 'alert_update') {
      setAlerts((a) => ['resolved', 'dismissed'].includes(data.status) ? a.filter((x) => x.id !== data.id) : a.map((x) => (x.id === data.id ? data : x)))
    }
    if (type === 'alert' || type === 'alert_update') api('/api/alerts/stats?hours=24').then(setStats).catch(() => {})
    if (type === 'news') setNews((n) => [data, ...n].slice(0, 5))
  })

  const byType = stats ? Object.entries(stats.by_type).sort((a, b) => b[1] - a[1]) : []
  const maxType = byType.length ? byType[0][1] : 1

  return (
    <div className="page">
      <div className="page-head">
        <h2>Operations overview</h2>
        <Link to="/report" className="btn primary">+ Report incident</Link>
      </div>
      <div className="stats">
        <Stat label="Active alerts" value={stats?.active} tone={stats?.active ? 'warn' : ''} />
        <Stat label="Awaiting review" value={stats?.pending_review} tone={stats?.pending_review ? 'info' : ''} />
        <Stat label="Critical (24h)" value={stats?.by_priority?.critical || 0} tone={stats?.by_priority?.critical ? 'danger' : ''} />
        <Stat label="Alerts (24h)" value={stats?.total} />
        <Stat label="Cameras online" value={`${cameras.filter((c) => c.status?.online).length}/${cameras.length}`} />
      </div>

      <div className="grid-2">
        <section className="card">
          <div className="card-head"><h3>Live alert feed</h3><Link to="/alerts" className="small">All alerts →</Link></div>
          {alerts.length === 0 ? <Empty>No active alerts. All clear.</Empty> : (
            <div className="list">{alerts.map((a) => <AlertRow key={a.id} alert={a} />)}</div>
          )}
        </section>
        <div className="stack">
          <section className="card">
            <div className="card-head"><h3>Last 24 hours by type</h3></div>
            {byType.length === 0 ? <Empty>No alerts in the last 24 hours</Empty> : byType.map(([k, v]) => (
              <div key={k} className="bar-row">
                <span className="bar-label small">{label(k)}</span>
                <span className="bar"><span style={{ width: `${(v / maxType) * 100}%` }} /></span>
                <span className="small">{v}</span>
              </div>
            ))}
            {stats && (
              <div className="prio-strip">
                {['critical', 'high', 'medium', 'low'].map((p) => (
                  <span key={p} className="small"><i style={{ background: PRIORITY_COLORS[p] }} />{label(p)} {stats.by_priority[p] || 0}</span>
                ))}
              </div>
            )}
          </section>
          <section className="card">
            <div className="card-head"><h3>Latest news</h3><Link to="/news" className="small">News →</Link></div>
            {news.length === 0 ? <Empty>No news yet</Empty> : news.map((n) => (
              <div key={n.id} className="news-mini">
                {n.is_important && <span className="badge prio-high">Important</span>} <strong>{n.title}</strong>
                <div className="muted small">{n.author.name} · {timeAgo(n.created_at)}</div>
              </div>
            ))}
          </section>
        </div>
      </div>

      <section className="card">
        <div className="card-head"><h3>Cameras</h3><Link to="/cameras" className="small">Full view →</Link></div>
        {cameras.length === 0 ? <Empty>No cameras yet. An admin can add them under Admin → Cameras.</Empty> : (
          <div className="camera-grid">
            {cameras.slice(0, 4).map((c) => <CameraTile key={c.id} camera={c} videoBase={config?.video_service_url} />)}
          </div>
        )}
      </section>
    </div>
  )
}

function UserDashboard() {
  const [campusAlerts, setCampusAlerts] = useState([])
  const [important, setImportant] = useState([])
  const [mine, setMine] = useState([])

  useEffect(() => {
    api('/api/alerts/public').then(setCampusAlerts).catch(() => {})
    api('/api/news?important=true&limit=5').then(setImportant).catch(() => {})
    api('/api/reports/mine').then(setMine).catch(() => {})
  }, [])

  useLiveEvent((type, data) => {
    if (type === 'campus_alert') setCampusAlerts((a) => [data, ...a.filter((x) => x.id !== data.id)])
    if (type === 'news' && data.is_important) setImportant((n) => [data, ...n].slice(0, 5))
  })

  return (
    <div className="page">
      <div className="page-head">
        <h2>Campus updates</h2>
        <Link to="/report" className="btn primary">+ Report incident</Link>
      </div>
      <div className="grid-2">
        <section className="card">
          <div className="card-head"><h3>Campus alerts</h3></div>
          {campusAlerts.length === 0 ? <Empty>No campus-wide alerts right now.</Empty> : campusAlerts.map((a) => (
            <AlertRow key={a.id} alert={a} />
          ))}
        </section>
        <section className="card">
          <div className="card-head"><h3>Important news</h3><Link to="/news" className="small">All news →</Link></div>
          {important.length === 0 ? <Empty>No important announcements.</Empty> : important.map((n) => (
            <div key={n.id} className="news-mini">
              <strong>{n.title}</strong>
              <p className="small">{n.body.slice(0, 220)}{n.body.length > 220 ? '…' : ''}</p>
              <div className="muted small">{timeAgo(n.created_at)}</div>
            </div>
          ))}
        </section>
      </div>
      <section className="card">
        <div className="card-head"><h3>My reports</h3></div>
        {mine.length === 0 ? <Empty>You have not reported anything yet.</Empty> : (
          <div className="list">{mine.map((a) => <AlertRow key={a.id} alert={a} />)}</div>
        )}
      </section>
    </div>
  )
}
