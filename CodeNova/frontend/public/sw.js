// Service worker: shows browser push notifications from the campus dashboard.
self.addEventListener('push', (event) => {
  let data = {}
  try { data = event.data ? event.data.json() : {} } catch { data = { title: 'Campus alert', body: event.data && event.data.text() } }
  const urgent = data.priority === 'critical' || data.priority === 'high'
  event.waitUntil(self.registration.showNotification(data.title || 'Campus alert', {
    body: data.body || '',
    icon: '/icon.svg',
    badge: '/icon.svg',
    tag: data.url || 'campus',
    requireInteraction: urgent,
    data: { url: data.url || '/' },
  }))
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const url = event.notification.data && event.notification.data.url || '/'
  event.waitUntil(clients.matchAll({ type: 'window', includeUncontrolled: true }).then((list) => {
    for (const c of list) { if ('focus' in c) { c.navigate(url); return c.focus() } }
    return clients.openWindow(url)
  }))
})
