// Browser push subscription (Web Push + service worker).
import { api } from './api'

function urlBase64ToUint8Array(base64) {
  const padding = '='.repeat((4 - (base64.length % 4)) % 4)
  const raw = atob((base64 + padding).replace(/-/g, '+').replace(/_/g, '/'))
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)))
}

export const pushSupported = () => 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window

export async function currentSubscription() {
  if (!pushSupported()) return null
  const reg = await navigator.serviceWorker.getRegistration('/sw.js')
  return reg ? reg.pushManager.getSubscription() : null
}

export async function enablePush(vapidKey) {
  if (!pushSupported()) throw new Error('This browser does not support push notifications')
  if (!vapidKey) throw new Error('Push is not configured on the server (VAPID keys missing in .env)')
  const perm = await Notification.requestPermission()
  if (perm !== 'granted') throw new Error('Notification permission was not granted')
  const reg = await navigator.serviceWorker.register('/sw.js')
  await navigator.serviceWorker.ready
  const sub = (await reg.pushManager.getSubscription()) ||
    (await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlBase64ToUint8Array(vapidKey) }))
  await api('/api/notifications/push/subscribe', { method: 'POST', body: sub.toJSON() })
  return sub
}

export async function disablePush() {
  const sub = await currentSubscription()
  if (!sub) return
  await api('/api/notifications/push/unsubscribe', { method: 'POST', body: { endpoint: sub.endpoint } }).catch(() => {})
  await sub.unsubscribe()
}
