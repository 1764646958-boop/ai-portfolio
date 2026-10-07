// CloudLoom Service Worker（D19）：静态资源缓存 + 导航离线兜底
// 明确不缓存 /api 与 /mcp：接口与 SSE 流必须实时（缓存会导致聊天/轮询拿到旧数据）
const CACHE = 'cloudloom-v1'
const ASSETS = ['/', '/index.html', '/manifest.webmanifest', '/favicon.svg']

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)).then(() => self.skipWaiting()))
})

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  )
})

self.addEventListener('fetch', (e) => {
  const req = e.request
  if (req.method !== 'GET') return
  const url = new URL(req.url)
  if (url.origin !== self.location.origin) return
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/mcp')) return

  if (req.mode === 'navigate') {
    e.respondWith(fetch(req).catch(() => caches.match('/index.html')))
    return
  }
  e.respondWith(
    caches.match(req).then((hit) => hit || fetch(req).then((res) => {
      if (res.ok && (url.pathname.startsWith('/assets/') || ASSETS.indexOf(url.pathname) >= 0)) {
        const clone = res.clone()
        caches.open(CACHE).then((c) => c.put(req, clone))
      }
      return res
    })),
  )
})
