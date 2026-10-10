import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import basicSsl from '@vitejs/plugin-basic-ssl'

// Backend (:8000) and video service (:8001) are reached through this server, so the
// browser only talks to one origin. Set HTTPS=1 to serve over HTTPS with a self-signed
// certificate: phones need HTTPS for GPS (geofenced reports) and push notifications.
const backend = process.env.BACKEND_URL || 'http://localhost:8000'
const video = process.env.VIDEO_URL || 'http://localhost:8001'
const https = process.env.HTTPS === '1'

const proxy = {
  '/api': backend,
  '/media': backend,
  '/ws': { target: backend.replace(/^http/, 'ws'), ws: true },
  '/video': { target: video, rewrite: (p) => p.replace(/^\/video/, '') },
}

export default defineConfig({
  plugins: [react(), ...(https ? [basicSsl()] : [])],
  server: { port: 5173, host: true, proxy },
  preview: { port: 5173, host: true, proxy },
})
