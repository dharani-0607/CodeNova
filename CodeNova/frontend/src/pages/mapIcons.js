import L from 'leaflet'
import { PRIORITY_COLORS } from '../lib/format'

// Inline SVG pins, so no external marker images are needed.
const cache = {}
export function pinIcon(priority = 'medium') {
  if (cache[priority]) return cache[priority]
  const color = PRIORITY_COLORS[priority] || '#2e90fa'
  cache[priority] = L.divIcon({
    className: 'pin',
    html: `<svg width="26" height="36" viewBox="0 0 26 36"><path d="M13 35s11-12.6 11-21A11 11 0 0 0 2 14c0 8.4 11 21 11 21z" fill="${color}" stroke="#fff" stroke-width="2"/><circle cx="13" cy="14" r="4" fill="#fff"/></svg>`,
    iconSize: [26, 36],
    iconAnchor: [13, 35],
    popupAnchor: [0, -30],
  })
  return cache[priority]
}

export const cameraIcon = L.divIcon({
  className: 'pin',
  html: '<div class="cam-pin">◉</div>',
  iconSize: [24, 24],
  iconAnchor: [12, 12],
})

export const meIcon = L.divIcon({
  className: 'pin',
  html: '<div class="me-pin"></div>',
  iconSize: [18, 18],
  iconAnchor: [9, 9],
})
