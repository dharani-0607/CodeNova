export const PRIORITIES = ['critical', 'high', 'medium', 'low']
export const STATUSES = ['pending_review', 'open', 'acknowledged', 'resolved', 'dismissed']

export const PRIORITY_COLORS = {
  critical: '#d92d20',
  high: '#f79009',
  medium: '#2e90fa',
  low: '#667085',
}

export function label(s) {
  return (s || '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

export function timeAgo(iso) {
  if (!iso) return ''
  const d = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : iso + 'Z')
  const s = Math.round((Date.now() - d.getTime()) / 1000)
  if (s < 60) return `${Math.max(s, 0)}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' })
}

export function dateTime(iso) {
  if (!iso) return ''
  const d = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : iso + 'Z')
  return d.toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}
