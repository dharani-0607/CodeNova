import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import 'leaflet/dist/leaflet.css'
import './styles.css'
import Layout from './components/Layout'
import { AuthProvider, useAuth } from './lib/auth'
import { LiveProvider } from './lib/live'
import Admin from './pages/Admin'
import AlertDetail from './pages/AlertDetail'
import Alerts from './pages/Alerts'
import Cameras from './pages/Cameras'
import Dashboard from './pages/Dashboard'
import Login from './pages/Login'
import MapPage from './pages/MapPage'
import Moderation from './pages/Moderation'
import News from './pages/News'
import Report from './pages/Report'

function Guard({ children, staff, admin }) {
  const { user, loading, isStaff, isAdmin } = useAuth()
  if (loading) return <div className="center-screen">Loading…</div>
  if (!user) return <Navigate to="/login" replace />
  if ((staff && !isStaff) || (admin && !isAdmin)) return <Navigate to="/" replace />
  return children
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<Guard><LiveProvider><Layout /></LiveProvider></Guard>}>
        <Route index element={<Dashboard />} />
        <Route path="cameras" element={<Guard staff><Cameras /></Guard>} />
        <Route path="alerts" element={<Guard staff><Alerts /></Guard>} />
        <Route path="alerts/:id" element={<AlertDetail />} />
        <Route path="map" element={<MapPage />} />
        <Route path="report" element={<Report />} />
        <Route path="news" element={<News />} />
        <Route path="moderation" element={<Guard staff><Moderation /></Guard>} />
        <Route path="admin/*" element={<Guard admin><Admin /></Guard>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <AuthProvider>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </AuthProvider>
  </StrictMode>,
)
