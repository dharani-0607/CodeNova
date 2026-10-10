import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { MapContainer, Marker, Polygon, Popup, TileLayer } from 'react-leaflet'
import { PriorityBadge } from '../components/ui'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { label, timeAgo } from '../lib/format'
import { useLiveEvent } from '../lib/live'
import { cameraIcon, pinIcon } from './mapIcons'

export default function MapPage() {
  const { config, isStaff } = useAuth()
  const [alerts, setAlerts] = useState([])
  const [cameras, setCameras] = useState([])
  const [hours, setHours] = useState(24)

  useEffect(() => {
    if (isStaff) {
      api(`/api/alerts?hours=${hours}&limit=500`).then(setAlerts).catch(() => {})
      api('/api/cameras').then(setCameras).catch(() => {})
    } else {
      Promise.all([api('/api/alerts/public'), api('/api/reports/mine')])
        .then(([a, b]) => setAlerts([...a, ...b.filter((x) => !a.some((y) => y.id === x.id))]))
        .catch(() => {})
    }
  }, [isStaff, hours])

  useLiveEvent((type, data) => {
    if ((isStaff && type === 'alert') || type === 'campus_alert') setAlerts((a) => [data, ...a.filter((x) => x.id !== data.id)])
  }, [isStaff])

  if (!config) return null
  const center = config.campus_center || [10.9027, 76.9006]
  const located = alerts.filter((a) => a.lat != null && a.lon != null)

  return (
    <div className="page">
      <div className="page-head">
        <h2>Campus map</h2>
        {isStaff && (
          <select value={hours} onChange={(e) => setHours(Number(e.target.value))}>
            <option value={1}>Last hour</option>
            <option value={24}>Last 24 hours</option>
            <option value={168}>Last 7 days</option>
            <option value={720}>Last 30 days</option>
          </select>
        )}
      </div>
      <div className="card map-card">
        <MapContainer center={center} zoom={16} style={{ height: 'calc(100vh - 210px)', minHeight: 380 }}>
          <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="© OpenStreetMap contributors" />
          {config.geofence && <Polygon positions={config.geofence} pathOptions={{ color: '#a4123f', fillOpacity: 0.06 }} />}
          {cameras.filter((c) => c.lat != null).map((c) => (
            <Marker key={`c${c.id}`} position={[c.lat, c.lon]} icon={cameraIcon}>
              <Popup><strong>{c.name}</strong><br />{c.location_name}<br />{c.status?.online ? 'Online' : 'Offline'} · {c.status?.people ?? 0} people</Popup>
            </Marker>
          ))}
          {located.map((a) => (
            <Marker key={a.id} position={[a.lat, a.lon]} icon={pinIcon(a.priority)}>
              <Popup>
                <strong>{a.title}</strong><br />
                <PriorityBadge priority={a.priority} /> {label(a.status)}<br />
                <span className="small">{timeAgo(a.created_at)}</span><br />
                <Link to={`/alerts/${a.id}`}>Open</Link>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>
      <p className="muted small">Red outline: campus geofence. Pins are coloured by priority. Camera alerts use the camera's position.</p>
    </div>
  )
}
