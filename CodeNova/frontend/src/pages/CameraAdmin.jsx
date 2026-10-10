import { useCallback, useEffect, useRef, useState } from 'react'
import { MapContainer, Marker, Polygon, TileLayer, useMapEvents } from 'react-leaflet'
import { ErrorNote, Modal } from '../components/ui'
import { api, videoUrl } from '../lib/api'
import { useAuth } from '../lib/auth'
import { label } from '../lib/format'
import { cameraIcon } from './mapIcons'

const ZONE_HELP = {
  restricted: 'Any person entering raises an intrusion alert. Params: active_from, active_to (HH:MM), min_seconds.',
  pedestrian: 'Cars, motorcycles, buses and trucks inside raise an alert.',
  no_parking: 'Vehicles stopped longer than max_seconds (default 120) raise an alert.',
  crowd: 'People counted here. Params: max_people, area_m2, max_density (people/m²), congestion_people.',
  after_hours: 'People staying longer than dwell_seconds after hours raise a loitering alert. Params: active_from, active_to, dwell_seconds.',
  littering: 'Littering detection only runs inside these zones (if any are drawn).',
}

const blankCamera = { name: '', source: '', location_name: '', lat: null, lon: null, enabled: true, detectors: null, calibration: {}, params: {} }

export default function CameraAdmin() {
  const [cameras, setCameras] = useState([])
  const [meta, setMeta] = useState({ detectors: [], zone_kinds: [] })
  const [editing, setEditing] = useState(null)
  const [zonesFor, setZonesFor] = useState(null)
  const [error, setError] = useState(null)

  const load = useCallback(() => api('/api/cameras').then(setCameras).catch(setError), [])
  useEffect(() => { load(); api('/api/cameras/detectors').then(setMeta) }, [load])

  const remove = async (c) => {
    if (!confirm(`Delete camera "${c.name}" and its zones?`)) return
    await api(`/api/cameras/${c.id}`, { method: 'DELETE' }).catch(setError)
    load()
  }

  return (
    <div className="stack">
      <div className="row gap"><button className="btn primary" onClick={() => setEditing({ ...blankCamera })}>+ Add camera</button></div>
      <ErrorNote error={error} />
      <div className="table-wrap card">
        <table className="table">
          <thead><tr><th>Name</th><th>Source</th><th>Location</th><th>Zones</th><th>Speed calibration</th><th>Status</th><th></th></tr></thead>
          <tbody>
            {cameras.map((c) => (
              <tr key={c.id}>
                <td><strong>{c.name}</strong>{!c.enabled && <span className="badge">disabled</span>}</td>
                <td className="small mono">{c.source}</td>
                <td className="small">{c.location_name}</td>
                <td>{c.zones.length}</td>
                <td className="small">{c.calibration?.distance_m ? `${c.calibration.distance_m} m` : '—'}</td>
                <td className="small">{c.status?.online ? 'Online' : 'Offline'}</td>
                <td className="nowrap">
                  <button className="btn small" onClick={() => setEditing(c)}>Edit</button>{' '}
                  <button className="btn small" onClick={() => setZonesFor(c)}>Zones & lines</button>{' '}
                  <button className="btn ghost small" onClick={() => remove(c)}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {editing && <CameraForm camera={editing} detectors={meta.detectors} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load() }} />}
      {zonesFor && <ZoneEditor camera={zonesFor} kinds={meta.zone_kinds} onClose={() => { setZonesFor(null); load() }} />}
    </div>
  )
}

function CameraForm({ camera, detectors, onClose, onSaved }) {
  const { config } = useAuth()
  const [c, setC] = useState(() => ({
    ...camera,
    detectors: camera.detectors && Object.keys(camera.detectors).length ? camera.detectors : Object.fromEntries(detectors.map((d) => [d, true])),
    paramsText: JSON.stringify(camera.params || {}, null, 1),
  }))
  const [error, setError] = useState(null)
  const set = (k) => (e) => setC({ ...c, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })

  const save = async (e) => {
    e.preventDefault()
    let params
    try { params = JSON.parse(c.paramsText || '{}') } catch { setError('Thresholds must be valid JSON'); return }
    const body = {
      name: c.name, source: c.source, location_name: c.location_name, enabled: c.enabled,
      lat: c.lat === '' || c.lat == null ? null : Number(c.lat), lon: c.lon === '' || c.lon == null ? null : Number(c.lon),
      detectors: c.detectors, calibration: c.calibration || {}, params,
    }
    try {
      await api(camera.id ? `/api/cameras/${camera.id}` : '/api/cameras', { method: camera.id ? 'PUT' : 'POST', body })
      onSaved()
    } catch (err) { setError(err) }
  }

  return (
    <Modal title={camera.id ? `Edit ${camera.name}` : 'Add camera'} onClose={onClose} wide>
      <form className="form" onSubmit={save}>
        <div className="grid-2">
          <div className="stack">
            <label>Name<input value={c.name} onChange={set('name')} required /></label>
            <label>Video source
              <input value={c.source} onChange={set('source')} required placeholder="rtsp://user:pass@10.0.0.5:554/stream1  |  0 (webcam)  |  samples/gate.mp4" />
            </label>
            <label>Location description<input value={c.location_name} onChange={set('location_name')} placeholder="Main gate, facing inward" /></label>
            <label className="check"><input type="checkbox" checked={c.enabled} onChange={set('enabled')} /> Enabled</label>
            <div>
              <div className="small"><strong>Detectors on this camera</strong></div>
              <div className="checks">
                {detectors.map((d) => (
                  <label key={d} className="check small">
                    <input type="checkbox" checked={!!c.detectors[d]} onChange={(e) => setC({ ...c, detectors: { ...c.detectors, [d]: e.target.checked } })} /> {label(d)}
                  </label>
                ))}
              </div>
            </div>
            <label>Thresholds (JSON)
              <textarea rows={4} className="mono small" value={c.paramsText} onChange={set('paramsText')}
                placeholder='{"crowd_warn": 30, "congestion_people": 12, "unattended_seconds": 60, "loiter_seconds": 60}' />
            </label>
          </div>
          <div className="stack">
            <div className="small"><strong>Position on map</strong> (click to place)</div>
            {config && (
              <MapContainer center={c.lat ? [c.lat, c.lon] : config.campus_center} zoom={16} style={{ height: 300 }}>
                <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="© OpenStreetMap" />
                <Polygon positions={config.geofence} pathOptions={{ color: '#a4123f', fillOpacity: 0.05 }} />
                <ClickToSet onClick={(lat, lon) => setC((x) => ({ ...x, lat: +lat.toFixed(6), lon: +lon.toFixed(6) }))} />
                {c.lat != null && c.lon != null && <Marker position={[c.lat, c.lon]} icon={cameraIcon} />}
              </MapContainer>
            )}
            <div className="row gap">
              <label className="grow">Lat<input value={c.lat ?? ''} onChange={set('lat')} /></label>
              <label className="grow">Lon<input value={c.lon ?? ''} onChange={set('lon')} /></label>
            </div>
          </div>
        </div>
        <ErrorNote error={error} />
        <div className="row gap"><button className="btn primary">Save</button><button type="button" className="btn ghost" onClick={onClose}>Cancel</button></div>
      </form>
    </Modal>
  )
}

function ClickToSet({ onClick }) {
  useMapEvents({ click: (e) => onClick(e.latlng.lat, e.latlng.lng) })
  return null
}

// Draw zones and speed lines on a live snapshot. Coordinates are stored normalised (0..1).
function ZoneEditor({ camera, kinds, onClose }) {
  const { config } = useAuth()
  const [zones, setZones] = useState(camera.zones)
  const [mode, setMode] = useState('zone') // zone | line_a | line_b
  const [points, setPoints] = useState([])
  const [draft, setDraft] = useState({ name: '', kind: kinds[0] || 'restricted', paramsText: '{}' })
  const [calib, setCalib] = useState(camera.calibration || {})
  const [snapKey, setSnapKey] = useState(Date.now())
  const [snapError, setSnapError] = useState(false)
  const [error, setError] = useState(null)
  const imgRef = useRef(null)

  const click = (e) => {
    const r = imgRef.current.getBoundingClientRect()
    const pt = [+((e.clientX - r.left) / r.width).toFixed(4), +((e.clientY - r.top) / r.height).toFixed(4)]
    if (mode === 'zone') setPoints((p) => [...p, pt])
    else {
      const next = [...points, pt]
      if (next.length === 2) { setCalib({ ...calib, [mode]: next }); setPoints([]) } else setPoints(next)
    }
  }

  const saveZone = async () => {
    let params
    try { params = JSON.parse(draft.paramsText || '{}') } catch { setError('Zone params must be valid JSON'); return }
    try {
      const z = await api(`/api/cameras/${camera.id}/zones`, { method: 'POST', body: { name: draft.name, kind: draft.kind, polygon: points, params } })
      setZones([...zones, z]); setPoints([]); setDraft({ ...draft, name: '' }); setError(null)
    } catch (err) { setError(err) }
  }

  const deleteZone = async (z) => {
    await api(`/api/cameras/zones/${z.id}`, { method: 'DELETE' })
    setZones(zones.filter((x) => x.id !== z.id))
  }

  const toggleZone = async (z) => {
    const updated = await api(`/api/cameras/zones/${z.id}`, { method: 'PUT', body: { name: z.name, kind: z.kind, polygon: z.polygon, params: z.params, enabled: !z.enabled } })
    setZones(zones.map((x) => (x.id === z.id ? updated : x)))
  }

  const saveCalib = async () => {
    const body = { ...camera, calibration: { ...calib, distance_m: calib.distance_m ? Number(calib.distance_m) : undefined } }
    delete body.zones; delete body.status; delete body.id
    try { await api(`/api/cameras/${camera.id}`, { method: 'PUT', body }); setError(null); alert('Speed calibration saved') } catch (err) { setError(err) }
  }

  const poly = (pts) => pts.map(([x, y]) => `${x * 100},${y * 100}`).join(' ')
  const line = (l, color) => l && <line x1={l[0][0] * 100} y1={l[0][1] * 100} x2={l[1][0] * 100} y2={l[1][1] * 100} stroke={color} strokeWidth="0.6" />

  return (
    <Modal title={`Zones & speed lines – ${camera.name}`} onClose={onClose} wide>
      <div className="grid-2 zone-editor">
        <div>
          <div className="row gap wrap">
            <button className={`btn small ${mode === 'zone' ? 'primary' : ''}`} onClick={() => { setMode('zone'); setPoints([]) }}>Draw zone</button>
            <button className={`btn small ${mode === 'line_a' ? 'primary' : ''}`} onClick={() => { setMode('line_a'); setPoints([]) }}>Speed line A</button>
            <button className={`btn small ${mode === 'line_b' ? 'primary' : ''}`} onClick={() => { setMode('line_b'); setPoints([]) }}>Speed line B</button>
            <button className="btn ghost small" onClick={() => { setSnapKey(Date.now()); setSnapError(false) }}>Refresh frame</button>
            {points.length > 0 && <button className="btn ghost small" onClick={() => setPoints([])}>Clear points</button>}
          </div>
          <div className="snapshot" onClick={click}>
            <img ref={imgRef} key={snapKey} src={videoUrl(config.video_service_url, 'snapshot', camera.id) + `&t=${snapKey}`} alt="Camera frame"
              onError={() => setSnapError(true)} onLoad={() => setSnapError(false)} draggable={false} />
            {snapError && <div className="snap-missing">No frame yet. Start the video service and make sure this camera's source works, then refresh.</div>}
            <svg viewBox="0 0 100 100" preserveAspectRatio="none">
              {zones.map((z) => <polygon key={z.id} points={poly(z.polygon)} className={`zone-shape kind-${z.kind} ${z.enabled ? '' : 'off'}`} />)}
              {mode === 'zone' && points.length > 0 && <polyline points={poly(points)} className="zone-draft" />}
              {mode === 'zone' && points.map(([x, y], i) => <circle key={i} cx={x * 100} cy={y * 100} r="0.8" fill="#fff" />)}
              {line(calib.line_a, '#facc15')}{line(calib.line_b, '#22d3ee')}
              {mode !== 'zone' && points.map(([x, y], i) => <circle key={i} cx={x * 100} cy={y * 100} r="0.8" fill="#facc15" />)}
            </svg>
          </div>
          <p className="muted small">
            {mode === 'zone' ? 'Click to add polygon corners (at least 3), then name and save the zone.'
              : `Click two points across the road for ${mode === 'line_a' ? 'line A' : 'line B'}.`}
          </p>
        </div>
        <div className="stack">
          <section>
            <h4>New zone</h4>
            <div className="form">
              <input placeholder="Zone name" value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
              <select value={draft.kind} onChange={(e) => setDraft({ ...draft, kind: e.target.value })}>
                {kinds.map((k) => <option key={k} value={k}>{label(k)}</option>)}
              </select>
              <div className="muted small">{ZONE_HELP[draft.kind]}</div>
              <textarea rows={2} className="mono small" value={draft.paramsText} onChange={(e) => setDraft({ ...draft, paramsText: e.target.value })} />
              <button className="btn primary small" disabled={points.length < 3 || !draft.name || mode !== 'zone'} onClick={saveZone}>Save zone ({points.length} pts)</button>
            </div>
          </section>
          <section>
            <h4>Zones</h4>
            {zones.length === 0 && <div className="muted small">No zones yet.</div>}
            {zones.map((z) => (
              <div key={z.id} className="row gap zone-item">
                <span className={`swatch kind-${z.kind}`} />
                <span className="grow small"><strong>{z.name}</strong> · {label(z.kind)} {!z.enabled && '(off)'}</span>
                <button className="btn ghost small" onClick={() => toggleZone(z)}>{z.enabled ? 'Disable' : 'Enable'}</button>
                <button className="btn ghost small" onClick={() => deleteZone(z)}>✕</button>
              </div>
            ))}
          </section>
          <section>
            <h4>Speed calibration</h4>
            <p className="muted small">Draw two lines across the road, then measure the real distance between them on the ground (e.g. with a tape or Google Maps). The speed limit is set in Admin → Campus settings.</p>
            <label className="small">Distance between line A and B (metres)
              <input type="number" min="1" step="0.1" value={calib.distance_m || ''} onChange={(e) => setCalib({ ...calib, distance_m: e.target.value })} />
            </label>
            <div className="small">Line A: {calib.line_a ? 'set' : '—'} · Line B: {calib.line_b ? 'set' : '—'}</div>
            <div className="row gap">
              <button className="btn small" onClick={saveCalib} disabled={!calib.line_a || !calib.line_b || !calib.distance_m}>Save calibration</button>
              <button className="btn ghost small" onClick={() => setCalib({})}>Clear</button>
            </div>
          </section>
          <ErrorNote error={error} />
        </div>
      </div>
    </Modal>
  )
}
