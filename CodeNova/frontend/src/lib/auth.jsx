import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api, getToken, setToken } from './api'

const AuthCtx = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [config, setConfig] = useState(null)
  const [loading, setLoading] = useState(true)

  const refreshConfig = useCallback(() => api('/api/config').then(setConfig).catch(() => {}), [])

  useEffect(() => {
    refreshConfig()
    if (!getToken()) { setLoading(false); return }
    api('/api/auth/me').then(setUser).catch(() => setToken(null)).finally(() => setLoading(false))
  }, [refreshConfig])

  useEffect(() => {
    const onLogout = () => setUser(null)
    window.addEventListener('campus-logout', onLogout)
    return () => window.removeEventListener('campus-logout', onLogout)
  }, [])

  const signIn = (token, u) => { setToken(token); setUser(u) }
  const signOut = () => { setToken(null); setUser(null) }
  const isStaff = user && (user.role === 'admin' || user.role === 'security')
  const isAdmin = user && user.role === 'admin'

  return (
    <AuthCtx.Provider value={{ user, config, loading, signIn, signOut, isStaff, isAdmin, refreshConfig }}>
      {children}
    </AuthCtx.Provider>
  )
}

export const useAuth = () => useContext(AuthCtx)
