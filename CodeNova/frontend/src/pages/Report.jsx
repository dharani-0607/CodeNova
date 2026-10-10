import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Circle, MapContainer, Marker, Polygon, TileLayer } from 'react-leaflet'
import { ErrorNote } from '../components/ui'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { label, PRIORITIES } from '../lib/format'
import { meIcon } from './mapIcons'

// Geofenced incident report: only accepted when the device's GPS is inside campus.
export default function Report() {
  const { config } = useAuth()
  const navigate = useNavigate()
  const [cats, setCats] = useState([])
  const [pos, setPos] = useState(null)
  const [geoError, setGeoError] = useState(null)
  const [check, setCheck] = useState(null)
  const [form, setForm] = useState({ category: '', title: '', description: '', priority: '', location_name: '' })
  const [photo, setPhoto] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => { api('/api/reports/categories').then((c) => { setCats(c); if (c[0]) setForm((f) => ({ ...f, category: c[0].key })) }) }, [])

  useEffect(() => {
    if (!('geolocation' in navigator)) { setGeoError('This device has no location support.'); return }
    const id = navigator.geolocation.watchPosition(
      (p) => { setGeoError(null); setPos({ lat: p.coords.latitude, lon: p.coords.longitude, accuracy: p.coords.accuracy }) },
      (e) => setGeoError(e.code === 1 ? 'Location permission denied. Allow location access to file a report.' : 'Could not get your location. Move outdoors and retry.'),
      { enableHighAccuracy: true, maximumAge: 10000, timeout: 20000 },
    )
    return () => navigator.geolocation.clearWatch(id)
  }, [])

  useEffect(() => {
    if (!pos) return
    const q = new URLSearchParams({ lat: pos.lat, lon: pos.lon, accuracy: Math.round(pos.accuracy) })
    api(`/api/reports/check?${q}`).then(setCheck).catch(() => {})
  }, [pos?.lat, pos?.lon, pos?.accuracy]) // eslint-disable-line react-hooks/exhaustive-deps

  const allowed = check && check.inside && check.accurate_enough
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })
  const selected = cats.find((c) => c.key === form.category)

  const submit = async (e) => {
    e.preventDefault()
    if (!allowed) return
    setBusy(true); setError(null)
    const fd = new FormData()
    Object.entries(form).forEach(([k, v]) => v && fd.append(k, v))
    fd.append('lat', pos.lat); fd.append('lon', pos.lon); fd.append('accuracy', pos.accuracy)
    if (photo) fd.append('photo', photo)
    try {
      const alert = await api('/api/reports', { method: 'POST', form: fd })
      navigate(`/alerts/${alert.id}`)
    } catch (err) { setError(err) } finally { setBusy(false) }
  }

  return (
    <div className="page">
      <div className="page-head"><h2>Report an incident</h2></div>
      <div className="grid-2">
        <form className="card form" onSubmit={submit}>
          <div className={`geo-status ${allowed ? 'ok' : 'bad'}`}>
            {geoError ? geoError
              : !pos ? 'Getting your location…'
              : !check ? 'Checking location…'
              : !check.inside ? 'You are outside the Amrita Coimbatore campus. Reports can only be filed from inside campus.'
              : !check.accurate_enough ? `GPS accuracy is ${Math.round(pos.accuracy)} m (need ${check.max_accuracy_m} m or better). Move outdoors and wait a moment.`
              : `Inside campus · GPS accuracy ${Math.round(pos.accuracy)} m`}
          </div>
          <label>Type of incident
            <select value={form.category} onChange={set('category')} required>
              {cats.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
            </select>
          </label>
          <label>Title<input value={form.title} onChange={set('title')} required minLength={3} maxLength={200} placeholder="Short summary" /></label>
          <label>What happened?<textarea rows={4} value={form.description} onChange={set('description')} maxLength={4000} /></label>
          <label>Landmark / building (optional)<input value={form.location_name} onChange={set('location_name')} placeholder="e.g. AB3 ground floor, near canteen" /></label>
          <label>Priority
            <select value={form.priority} onChange={set('priority')}>
              <option value="">Default for this type ({label(selected?.default_priority)})</option>
              {PRIORITIES.map((p) => <option key={p} value={p}>{label(p)}</option>)}
            </select>
          </label>
          <label>Photo (optional)<input type="file" accept="image/*" capture="environment" onChange={(e) => setPhoto(e.target.files[0] || null)} /></label>
          <ErrorNote error={error} />
          <button className="btn primary" disabled={!allowed || busy}>{busy ? 'Sending…' : 'Submit report'}</button>
          <p className="muted small">Your name, email and location are shared with campus security. For life-threatening emergencies also call security directly.</p>
        </form>
        <div className="card map-card">
          {config && (
            <MapContainer center={pos ? [pos.lat, pos.lon] : config.campus_center} zoom={16} style={{ height: 420 }}>
              <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="© OpenStreetMap" />
              <Polygon positions={config.geofence} pathOptions={{ color: '#a4123f', fillOpacity: 0.06 }} />
              {pos && <Marker position={[pos.lat, pos.lon]} icon={meIcon} />}
              {pos && <Circle center={[pos.lat, pos.lon]} radius={pos.accuracy} pathOptions={{ color: '#2e90fa', weight: 1 }} />}
            </MapContainer>
          )}
        </div>
      </div>
    </div>
  )
}
