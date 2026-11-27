/**
 * ATENEA Progressive Web App Service Worker
 *
 * Security & Multi-Tenant Invariant:
 * Never intercept or cache /api/*, /ws/*, /metrics, /health, /docs, /redoc, or /openapi.json.
 * Only static App Shell assets are cached locally.
 */
const CACHE_PREFIX = 'atenea-app-shell-'
const CACHE_VERSION = '__ATENEA_SW_VERSION__'
const CACHE_NAME = `${CACHE_PREFIX}${CACHE_VERSION}`

const DEFAULT_SHELL_URLS = [
  '/',
  '/index.html',
  '/manifest.webmanifest',
  '/atenea-icon.png',
  '/pwa-192x192.png',
  '/pwa-512x512.png',
  '/pwa-maskable-512x512.png',
]

// Replaced at build time by ateneaPwaPlugin in vite.config.ts with hashed /assets/* bundles
const BUILD_INJECTED_URLS = [/* __ATENEA_PRECACHE_MANIFEST__ */]
const PRECACHE_URLS = Array.from(new Set([...DEFAULT_SHELL_URLS, ...BUILD_INJECTED_URLS]))

const BYPASSED_PATH_PREFIXES = ['/api/', '/ws/']
const BYPASSED_EXACT_PATHS = new Set(['/api', '/ws', '/health', '/metrics', '/docs', '/redoc', '/openapi.json'])

function isBypassedPath(pathname) {
  if (BYPASSED_EXACT_PATHS.has(pathname)) {
    return true
  }
  return BYPASSED_PATH_PREFIXES.some((prefix) => pathname.startsWith(prefix))
}

function isCacheableResponse(response) {
  if (!response || response.status !== 200) {
    return false
  }
  return !response.type || response.type === 'basic'
}

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting()),
  )
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key.startsWith(CACHE_PREFIX) && key !== CACHE_NAME)
            .map((staleKey) => caches.delete(staleKey)),
        ),
      )
      .then(() => self.clients.claim()),
  )
})

self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    void self.skipWaiting()
  }
})

async function handleNavigationRequest(request) {
  try {
    const networkResponse = await fetch(request)
    if (isCacheableResponse(networkResponse)) {
      const cache = await caches.open(CACHE_NAME)
      await cache.put('/index.html', networkResponse.clone())
    }
    return networkResponse
  } catch {
    const cachedShell = (await caches.match('/index.html')) || (await caches.match('/'))
    if (cachedShell) {
      return cachedShell
    }
    throw new Error('ATENEA offline and App Shell not yet cached')
  }
}

async function handleImmutableAssetRequest(request) {
  const cached = await caches.match(request)
  if (cached) {
    return cached
  }
  const networkResponse = await fetch(request)
  if (isCacheableResponse(networkResponse)) {
    const cache = await caches.open(CACHE_NAME)
    await cache.put(request, networkResponse.clone())
  }
  return networkResponse
}

async function handleStaleWhileRevalidate(request) {
  const cache = await caches.open(CACHE_NAME)
  const cached = await cache.match(request)
  const networkFetch = fetch(request)
    .then(async (response) => {
      if (isCacheableResponse(response)) {
        await cache.put(request, response.clone())
      }
      return response
    })
    .catch(() => undefined)

  if (cached) {
    return cached
  }
  const fresh = await networkFetch
  if (fresh) {
    return fresh
  }
  throw new Error('Static asset unavailable offline')
}

self.addEventListener('fetch', (event) => {
  const { request } = event
  if (request.method !== 'GET') {
    return
  }

  let parsedUrl
  try {
    parsedUrl = new URL(request.url)
  } catch {
    return
  }

  if (parsedUrl.origin !== self.location.origin) {
    return
  }

  if (isBypassedPath(parsedUrl.pathname)) {
    return
  }

  if (request.mode === 'navigate') {
    event.respondWith(handleNavigationRequest(request))
    return
  }

  if (parsedUrl.pathname.startsWith('/assets/')) {
    event.respondWith(handleImmutableAssetRequest(request))
    return
  }

  event.respondWith(handleStaleWhileRevalidate(request))
})

