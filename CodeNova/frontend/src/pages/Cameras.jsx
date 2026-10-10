import { useEffect, useState } from 'react'
import { CameraTile, Empty, ErrorNote } from '../components/ui'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'

export default function Cameras() {
  const { config } = useAuth()
  const [cameras, setCameras] = useState(null)
  const [error, setError] = useState(null)
  const [focus, setFocus] = useState(null)
  const [cols, setCols] = useState(2)

  useEffect(() => { api('/api/cameras').then(setCameras).catch(setError) }, [])

  if (error) return <ErrorNote error={error} />
  if (!cameras) return <div className="muted">Loading cameras…</div>
  const focused = cameras.find((c) => c.id === focus)

  return (
    <div className="page">
      <div className="page-head">
        <h2>Live cameras</h2>
        <div className="row gap">
          {[1, 2, 3].map((n) => (
            <button key={n} className={`btn small ${cols === n ? 'primary' : 'ghost'}`} onClick={() => setCols(n)}>{n}×</button>
          ))}
        </div>
      </div>
      {cameras.length === 0 && <Empty>No cameras configured. Add them in Admin → Cameras.</Empty>}
      {focused && (
        <div className="card">
          <div className="card-head"><h3>{focused.name}</h3><button className="btn ghost small" onClick={() => setFocus(null)}>Close</button></div>
          <CameraTile camera={focused} videoBase={config?.video_service_url} large />
        </div>
      )}
      <div className="camera-grid" style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}>
        {cameras.map((c) => (
          <div key={c.id} onClick={() => setFocus(c.id)} className="clickable">
            <CameraTile camera={c} videoBase={config?.video_service_url} />
          </div>
        ))}
      </div>
      <p className="muted small">Streams come from the video analytics service at {config?.video_service_url}. Boxes, zones and live counts are drawn by the detection models.</p>
    </div>
  )
}
