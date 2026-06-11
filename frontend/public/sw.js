// Ashborne Silicon — minimal service worker.
// Strategy: never cache API responses (data must stay fresh); cache the app
// shell + static assets so the installed PWA opens instantly and works offline
// for navigation. Bump CACHE_VERSION to invalidate old caches on deploy.
const CACHE_VERSION = 'ashborne-v1'
const SHELL = ['/', '/index.html', '/ashborne-logo.png', '/manifest.webmanifest']

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) => cache.addAll(SHELL)).catch(() => {}),
  )
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_VERSION).map((k) => caches.delete(k))),
    ),
  )
  self.clients.claim()
})

self.addEventListener('fetch', (event) => {
  const { request } = event
  if (request.method !== 'GET') return

  const url = new URL(request.url)
  // Never intercept API traffic — always hit the network for live job data.
  if (url.pathname.startsWith('/api') || url.hostname !== self.location.hostname) return

  // Navigations: network-first, fall back to cached shell when offline.
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((res) => {
          const copy = res.clone()
          caches.open(CACHE_VERSION).then((c) => c.put(request, copy)).catch(() => {})
          return res
        })
        .catch(() => caches.match(request).then((r) => r || caches.match('/index.html'))),
    )
    return
  }

  // Static assets: cache-first, then network (and cache the result).
  event.respondWith(
    caches.match(request).then(
      (cached) =>
        cached ||
        fetch(request).then((res) => {
          if (res && res.status === 200 && res.type === 'basic') {
            const copy = res.clone()
            caches.open(CACHE_VERSION).then((c) => c.put(request, copy)).catch(() => {})
          }
          return res
        }),
    ),
  )
})
