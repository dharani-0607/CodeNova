import { useCallback, useEffect, useState } from 'react'
import { Empty, ErrorNote } from '../components/ui'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { label, timeAgo } from '../lib/format'
import { useLiveEvent } from '../lib/live'

export default function News() {
  const { user, isStaff } = useAuth()
  const [posts, setPosts] = useState(null)
  const [cats, setCats] = useState([])
  const [category, setCategory] = useState('')
  const [form, setForm] = useState({ title: '', body: '', category: 'general', is_important: false })
  const [notice, setNotice] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    api(`/api/news${category ? `?category=${category}` : ''}`).then(setPosts).catch(setError)
  }, [category])
  useEffect(() => { load() }, [load])
  useEffect(() => { api('/api/news/categories').then(setCats) }, [])
  useLiveEvent((type) => { if (['news', 'comment', 'news_deleted'].includes(type)) load() }, [load])

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setError(null); setNotice(null)
    try {
      const r = await api('/api/news', { method: 'POST', body: form })
      setNotice({ ok: r.post.status === 'published', text: r.message })
      if (r.post.status === 'published') setForm({ title: '', body: '', category: 'general', is_important: false })
      load()
    } catch (err) { setError(err) } finally { setBusy(false) }
  }

  const remove = async (id) => {
    if (!confirm('Delete this post?')) return
    await api(`/api/news/${id}`, { method: 'DELETE' }).catch(setError)
    load()
  }

  return (
    <div className="page">
      <div className="page-head">
        <h2>Campus news</h2>
        <select value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">All categories</option>
          {cats.map((c) => <option key={c} value={c}>{label(c)}</option>)}
        </select>
      </div>
      <form className="card form" onSubmit={submit}>
        <h3>Post an update</h3>
        <div className="row gap wrap">
          <input className="grow" placeholder="Headline" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required minLength={3} maxLength={200} />
          <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
            {cats.map((c) => <option key={c} value={c}>{label(c)}</option>)}
          </select>
        </div>
        <textarea rows={3} placeholder="Campus-related news only. Posts are checked by AI moderation." value={form.body}
          onChange={(e) => setForm({ ...form, body: e.target.value })} required minLength={3} maxLength={10000} />
        <div className="row gap wrap">
          {isStaff && (
            <label className="check"><input type="checkbox" checked={form.is_important} onChange={(e) => setForm({ ...form, is_important: e.target.checked })} />
              Important (notify everyone by push and email)</label>
          )}
          <button className="btn primary" disabled={busy}>{busy ? 'Checking…' : 'Publish'}</button>
        </div>
        {notice && <div className={notice.ok ? 'info-note' : 'error-note'}>{notice.text}</div>}
        <ErrorNote error={error} />
      </form>

      {posts && posts.length === 0 && <Empty>No news yet.</Empty>}
      {posts && posts.map((p) => (
        <Post key={p.id} post={p} me={user} isStaff={isStaff} onDelete={() => remove(p.id)} onChange={load} />
      ))}
    </div>
  )
}

function Post({ post, me, isStaff, onDelete, onChange }) {
  const [comment, setComment] = useState('')
  const [msg, setMsg] = useState(null)
  const send = async (e) => {
    e.preventDefault()
    try {
      const r = await api(`/api/news/${post.id}/comments`, { method: 'POST', body: { body: comment } })
      setMsg(r.comment.status === 'published' ? null : r.message)
      setComment('')
      onChange()
    } catch (err) { setMsg(err.message) }
  }
  return (
    <article className={`card post ${post.is_important ? 'important' : ''}`}>
      <div className="post-head">
        <div>
          {post.is_important && <span className="badge prio-high">Important</span>}
          {post.is_official && <span className="badge">Official</span>}
          <span className="badge">{label(post.category)}</span>
          {post.status !== 'published' && <span className={`badge status-${post.status}`}>{label(post.status)} – only you can see this</span>}
          <h3>{post.title}</h3>
          <div className="muted small">{post.author.name} · {timeAgo(post.created_at)}</div>
        </div>
        {(post.author.id === me.id || isStaff) && <button className="btn ghost small" onClick={onDelete}>Delete</button>}
      </div>
      <p className="pre">{post.body}</p>
      {post.status !== 'published' && post.moderation?.reasons?.length > 0 && (
        <div className="error-note small">Moderation: {post.moderation.reasons.join('; ')}</div>
      )}
      <div className="comments">
        {post.comments.map((c) => (
          <div key={c.id} className="comment">
            <strong className="small">{c.author.name}</strong> <span className="muted small">{timeAgo(c.created_at)}</span>
            {c.status !== 'published' && <span className={`badge status-${c.status}`}>{label(c.status)}</span>}
            <div>{c.body}</div>
          </div>
        ))}
        {post.status === 'published' && (
          <form onSubmit={send} className="row gap">
            <input className="grow" placeholder="Write a comment…" value={comment} onChange={(e) => setComment(e.target.value)} required maxLength={2000} />
            <button className="btn small">Comment</button>
          </form>
        )}
        {msg && <div className="error-note small">{msg}</div>}
      </div>
    </article>
  )
}
