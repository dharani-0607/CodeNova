import { useCallback, useEffect, useState } from 'react'
import { Empty, ErrorNote } from '../components/ui'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { label, timeAgo } from '../lib/format'
import { useLiveEvent } from '../lib/live'

export default function Moderation() {
  const { isAdmin } = useAuth()
  const [queue, setQueue] = useState(null)
  const [showRemoved, setShowRemoved] = useState(false)
  const [error, setError] = useState(null)

  const load = useCallback(() => {
    api(`/api/moderation/queue?include_removed=${showRemoved}`).then(setQueue).catch(setError)
  }, [showRemoved])
  useEffect(() => { load() }, [load])
  useLiveEvent((type) => { if (type === 'moderation') load() }, [load])

  const decide = async (kind, id, decision) => {
    await api(`/api/moderation/${kind}/${id}`, { method: 'POST', body: { decision } }).catch(setError)
    load()
  }

  return (
    <div className="page">
      <div className="page-head">
        <h2>Content moderation</h2>
        <label className="check"><input type="checkbox" checked={showRemoved} onChange={(e) => setShowRemoved(e.target.checked)} /> Show auto-removed too</label>
      </div>
      <p className="muted">Posts and comments the AI held for review (or removed). Approve to publish, or remove.</p>
      <ErrorNote error={error} />
      {queue && queue.posts.length + queue.comments.length === 0 && <Empty>Queue is empty.</Empty>}
      {queue && queue.posts.map((p) => (
        <QueueItem key={`p${p.id}`} kind="post" id={p.id} title={p.title} body={p.body} author={p.author.name}
          created={p.created_at} status={p.status} moderation={p.moderation} onDecide={decide} />
      ))}
      {queue && queue.comments.map((c) => (
        <QueueItem key={`c${c.id}`} kind="comment" id={c.id} title={`Comment on "${c.post_title}"`} body={c.body}
          author={c.author.name} created={c.created_at} status={c.status} moderation={c.moderation} onDecide={decide} />
      ))}
      {isAdmin && <TryIt />}
    </div>
  )
}

function QueueItem({ kind, id, title, body, author, created, status, moderation, onDecide }) {
  return (
    <div className="card">
      <div className="post-head">
        <div>
          <span className={`badge status-${status}`}>{label(status)}</span> <span className="badge">{kind}</span>
          <h3>{title}</h3>
          <div className="muted small">{author} · {timeAgo(created)}</div>
        </div>
        <div className="row gap">
          <button className="btn success small" onClick={() => onDecide(kind, id, 'published')}>Approve</button>
          {status !== 'removed' && <button className="btn danger small" onClick={() => onDecide(kind, id, 'removed')}>Remove</button>}
        </div>
      </div>
      <p className="pre">{body}</p>
      <ModerationReasons m={moderation} />
    </div>
  )
}

function ModerationReasons({ m }) {
  if (!m) return null
  return (
    <div className="small">
      {m.reasons?.length > 0 && <div className="error-note">Reasons: {m.reasons.join('; ')}</div>}
      {m.scores && Object.keys(m.scores).length > 0 && (
        <div className="scores">
          {Object.entries(m.scores).map(([k, v]) => (
            <span key={k} className="score"><span>{label(k)}</span><span className="bar"><span style={{ width: `${v * 100}%` }} /></span>{(v * 100).toFixed(0)}%</span>
          ))}
        </div>
      )}
      {m.model_used === false && <div className="muted">AI model not loaded; only campus rules were applied.</div>}
    </div>
  )
}

function TryIt() {
  const [text, setText] = useState('')
  const [result, setResult] = useState(null)
  const run = async (e) => {
    e.preventDefault()
    setResult(await api('/api/moderation/test', { method: 'POST', body: { text } }).catch((err) => ({ error: err.message })))
  }
  return (
    <form className="card form" onSubmit={run}>
      <h3>Test the moderation model</h3>
      <textarea rows={3} value={text} onChange={(e) => setText(e.target.value)} placeholder="Type any text to see what moderation would decide" required />
      <button className="btn small">Check</button>
      {result?.error && <div className="error-note">{result.error}</div>}
      {result?.decision && (<><div><strong>Decision:</strong> {label(result.decision)}</div><ModerationReasons m={result} /></>)}
    </form>
  )
}
