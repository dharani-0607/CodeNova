import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { ErrorNote } from '../components/ui'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'

export default function Login() {
  const { user, signIn, config } = useAuth()
  const navigate = useNavigate()
  const [mode, setMode] = useState('login') // login | register | verify
  const [form, setForm] = useState({ email: '', password: '', name: '', code: '' })
  const [error, setError] = useState(null)
  const [info, setInfo] = useState(null)
  const [busy, setBusy] = useState(false)
  const domain = config?.email_domain || 'cb.amrita.edu'

  if (user) return <Navigate to="/" replace />
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  const submit = async (e) => {
    e.preventDefault()
    setError(null); setInfo(null)
    if (mode !== 'verify' && !form.email.toLowerCase().endsWith('@' + domain)) {
      setError(`Use your @${domain} email address`)
      return
    }
    setBusy(true)
    try {
      if (mode === 'login') {
        const r = await api('/api/auth/login', { method: 'POST', body: { email: form.email, password: form.password } })
        signIn(r.token, r.user); navigate('/')
      } else if (mode === 'register') {
        const r = await api('/api/auth/register', { method: 'POST', body: { email: form.email, password: form.password, name: form.name } })
        if (r.token) { signIn(r.token, r.user); navigate('/') } else {
          setMode('verify'); setInfo(`We sent a 6-digit code to ${form.email}.`)
        }
      } else {
        const r = await api('/api/auth/verify', { method: 'POST', body: { email: form.email, code: form.code } })
        signIn(r.token, r.user); navigate('/')
      }
    } catch (err) {
      if (mode === 'login' && err.status === 403 && /verified/i.test(err.message)) {
        setMode('verify'); setInfo(err.message)
      } else setError(err)
    } finally { setBusy(false) }
  }

  const resend = async () => {
    await api('/api/auth/resend', { method: 'POST', body: { email: form.email } }).catch(() => {})
    setInfo('A new code has been sent.')
  }

  return (
    <div className="login-page">
      <div className="login-card card">
        <div className="login-brand">
          <img src="/icon.svg" alt="" />
          <div>
            <h1>Campus Command Center</h1>
            <div className="muted">Amrita Vishwa Vidyapeetham, Coimbatore</div>
          </div>
        </div>
        {mode !== 'verify' && (
          <div className="tabs">
            <button className={mode === 'login' ? 'active' : ''} onClick={() => setMode('login')}>Sign in</button>
            <button className={mode === 'register' ? 'active' : ''} onClick={() => setMode('register')}>Register</button>
          </div>
        )}
        <form onSubmit={submit} className="form">
          {mode === 'register' && (
            <label>Full name<input value={form.name} onChange={set('name')} required minLength={2} /></label>
          )}
          <label>Campus email
            <input type="email" value={form.email} onChange={set('email')} placeholder={`you@${domain}`} required disabled={mode === 'verify'} />
          </label>
          {mode !== 'verify' && (
            <label>Password<input type="password" value={form.password} onChange={set('password')} required minLength={8} /></label>
          )}
          {mode === 'verify' && (
            <label>Verification code
              <input value={form.code} onChange={set('code')} inputMode="numeric" maxLength={6} required autoFocus />
            </label>
          )}
          {info && <div className="info-note">{info}</div>}
          <ErrorNote error={error} />
          <button className="btn primary" disabled={busy}>
            {busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : mode === 'register' ? 'Create account' : 'Verify'}
          </button>
          {mode === 'verify' && (
            <div className="row gap">
              <button type="button" className="btn ghost small" onClick={resend}>Resend code</button>
              <button type="button" className="btn ghost small" onClick={() => setMode('login')}>Back</button>
            </div>
          )}
        </form>
        <p className="muted small">Only @{domain} accounts can sign in. Incident reports also require your device to be inside the campus.</p>
      </div>
    </div>
  )
}
