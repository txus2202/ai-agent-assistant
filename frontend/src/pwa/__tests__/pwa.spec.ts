import { readFileSync, existsSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, it, expect, vi } from 'vitest'
import { registerAteneaServiceWorker } from '../registerServiceWorker'

const frontendRoot = resolve(__dirname, '../../..')
const publicDir = resolve(frontendRoot, 'public')

interface MockFetchEvent {
  request: {
    method: string
    url: string
    mode?: string
  }
  respondWith: ReturnType<typeof vi.fn>
}

type SwListener = (event: Record<string, unknown>) => void

function loadServiceWorkerInSandbox(overrides?: {
  fetchImpl?: (req: unknown) => Promise<unknown>
  initialCacheEntries?: Record<string, Record<string, unknown>>
}) {
  const swCode = readFileSync(resolve(publicDir, 'sw.js'), 'utf-8')
  const listeners: Record<string, SwListener[]> = {}
  const cacheStore = new Map<string, Map<string, unknown>>()

  if (overrides?.initialCacheEntries) {
    for (const [cacheName, entries] of Object.entries(overrides.initialCacheEntries)) {
      cacheStore.set(cacheName, new Map(Object.entries(entries)))
    }
  }

  const normalizeKey = (reqOrUrl: unknown): string => {
    if (typeof reqOrUrl === 'string') {
      return new URL(reqOrUrl, 'https://atenea.local').pathname
    }
    if (reqOrUrl && typeof reqOrUrl === 'object' && 'url' in reqOrUrl) {
      return new URL((reqOrUrl as { url: string }).url, 'https://atenea.local').pathname
    }
    return String(reqOrUrl)
  }

  const cachesMock = {
    open: vi.fn(async (name: string) => {
      if (!cacheStore.has(name)) {
        cacheStore.set(name, new Map())
      }
      const bucket = cacheStore.get(name)!
      return {
        addAll: vi.fn(async (urls: string[]) => {
          for (const u of urls) {
            bucket.set(normalizeKey(u), { status: 200, ok: true, url: u, clone: () => ({ status: 200, ok: true, url: u }) })
          }
        }),
        match: vi.fn(async (req: unknown) => bucket.get(normalizeKey(req))),
        put: vi.fn(async (req: unknown, res: unknown) => {
          bucket.set(normalizeKey(req), res)
        }),
      }
    }),
    keys: vi.fn(async () => Array.from(cacheStore.keys())),
    delete: vi.fn(async (name: string) => cacheStore.delete(name)),
    match: vi.fn(async (req: unknown) => {
      for (const bucket of cacheStore.values()) {
        const hit = bucket.get(normalizeKey(req))
        if (hit) return hit
      }
      return undefined
    }),
  }

  const skipWaiting = vi.fn(async () => undefined)
  const claim = vi.fn(async () => undefined)
  const fetchMock = vi.fn(
    overrides?.fetchImpl ??
      (async (req: unknown) => {
        const res = { status: 200, ok: true, type: 'basic', url: normalizeKey(req), clone: () => ({ ...res }) }
        return res
      }),
  )

  const selfMock = {
    location: new URL('https://atenea.local/sw.js'),
    caches: cachesMock,
    fetch: fetchMock,
    skipWaiting,
    clients: { claim },
    addEventListener: (type: string, cb: SwListener) => {
      listeners[type] = listeners[type] || []
      listeners[type].push(cb)
    },
  }

  const runner = new Function('self', 'caches', 'fetch', swCode)
  runner(selfMock, cachesMock, fetchMock)

  return { listeners, cachesMock, cacheStore, skipWaiting, claim, fetchMock }
}

describe('Progressive Web App (PWA) Manifest, Assets, Nginx & Service Worker', () => {
  it('defines a valid W3C manifest.webmanifest with explicit id, standalone display, and existing PNG icons', () => {
    const manifestPath = resolve(publicDir, 'manifest.webmanifest')
    expect(existsSync(manifestPath)).toBe(true)

    const manifest = JSON.parse(readFileSync(manifestPath, 'utf-8')) as {
      id: string
      name: string
      short_name: string
      start_url: string
      scope: string
      display: string
      theme_color: string
      background_color: string
      icons: Array<{ src: string; sizes: string; type: string; purpose?: string }>
    }

    expect(manifest.id).toBe('/')
    expect(manifest.start_url).toBe('/')
    expect(manifest.scope).toBe('/')
    expect(manifest.display).toBe('standalone')
    expect(manifest.theme_color).toBe('#05070c')
    expect(manifest.background_color).toBe('#05070c')
    expect(manifest.name.trim().length).toBeGreaterThan(0)
    expect(manifest.short_name.trim().length).toBeGreaterThan(0)

    const has192 = manifest.icons.some((i) => i.sizes === '192x192' && i.purpose === 'any')
    const has512 = manifest.icons.some((i) => i.sizes === '512x512' && i.purpose === 'any')
    const hasMaskable = manifest.icons.some((i) => i.sizes === '512x512' && i.purpose === 'maskable')
    expect(has192).toBe(true)
    expect(has512).toBe(true)
    expect(hasMaskable).toBe(true)

    for (const icon of manifest.icons) {
      const iconFile = resolve(publicDir, icon.src.replace(/^\//, ''))
      expect(existsSync(iconFile)).toBe(true)
    }
  })

  it('links /manifest.webmanifest and sets lang="es" in index.html', () => {
    const indexHtml = readFileSync(resolve(frontendRoot, 'index.html'), 'utf-8')
    expect(indexHtml).toContain('lang="es"')
    expect(indexHtml).toContain('rel="manifest" href="/manifest.webmanifest"')
  })

  it('configures nginx.conf with application/manifest+json MIME type and no-cache headers for sw.js and manifest.webmanifest', () => {
    const nginxConf = readFileSync(resolve(frontendRoot, 'nginx.conf'), 'utf-8')
    expect(nginxConf).toContain('location = /manifest.webmanifest')
    expect(nginxConf).toContain('application/manifest+json')
    expect(nginxConf).toContain('location = /sw.js')
    expect(nginxConf).toContain('no-cache, no-store, must-revalidate')
  })

  it('never intercepts /api/*, /ws/*, /metrics, /health, or non-GET requests (strict multi-tenant boundary)', () => {
    const { listeners } = loadServiceWorkerInSandbox()
    const fetchHandlers = listeners.fetch || []
    expect(fetchHandlers.length).toBeGreaterThan(0)

    const bypassedUrls = [
      { method: 'GET', url: 'https://atenea.local/api/auth/me' },
      { method: 'GET', url: 'https://atenea.local/api/config/topology' },
      { method: 'GET', url: 'https://atenea.local/ws/debate' },
      { method: 'GET', url: 'https://atenea.local/ws/voice' },
      { method: 'GET', url: 'https://atenea.local/metrics' },
      { method: 'GET', url: 'https://atenea.local/health' },
      { method: 'POST', url: 'https://atenea.local/index.html' },
      { method: 'GET', url: 'https://fonts.googleapis.com/css2?family=Inter' },
    ]

    for (const req of bypassedUrls) {
      const respondWith = vi.fn()
      const event: MockFetchEvent = { request: req, respondWith }
      fetchHandlers[0]!(event as unknown as Record<string, unknown>)
      expect(respondWith).not.toHaveBeenCalled()
    }
  })

  it('falls back to cached /index.html on offline navigation and purges stale caches on activate', async () => {
    const cachedIndex = { status: 200, ok: true, body: 'cached-app-shell' }
    const { listeners, cacheStore, claim } = loadServiceWorkerInSandbox({
      fetchImpl: async () => {
        throw new Error('Offline network failure')
      },
      initialCacheEntries: {
        'atenea-app-shell-old-v0': { '/index.html': { stale: true } },
        'atenea-app-shell-__ATENEA_SW_VERSION__': { '/index.html': cachedIndex },
      },
    })

    // 1. Activate should delete old cache and keep current version
    const waitUntilPromises: Promise<unknown>[] = []
    listeners.activate![0]!({
      waitUntil: (p: Promise<unknown>) => waitUntilPromises.push(p),
    })
    await Promise.all(waitUntilPromises)
    expect(cacheStore.has('atenea-app-shell-old-v0')).toBe(false)
    expect(cacheStore.has('atenea-app-shell-__ATENEA_SW_VERSION__')).toBe(true)
    expect(claim).toHaveBeenCalledOnce()

    // 2. Navigate request when offline falls back to cached /index.html
    let responsePromise: Promise<unknown> | undefined
    listeners.fetch![0]!({
      request: {
        method: 'GET',
        url: 'https://atenea.local/topology',
        mode: 'navigate',
      },
      respondWith: (p: Promise<unknown>) => {
        responsePromise = p
      },
    })
    expect(responsePromise).toBeDefined()
    const resolved = await responsePromise
    expect(resolved).toEqual(cachedIndex)
  })

  it('registers /sw.js only in production secure contexts with updateViaCache: none', async () => {
    const registerSpy = vi.fn().mockResolvedValue({ update: vi.fn() })
    const fakeNavigator = { serviceWorker: { register: registerSpy } }

    // Skipped in dev/test mode
    const devRes = await registerAteneaServiceWorker({
      isProd: false,
      isSecureContext: true,
      navigatorObj: fakeNavigator,
    })
    expect(devRes).toBeNull()
    expect(registerSpy).not.toHaveBeenCalled()

    // Skipped in insecure HTTP LAN context
    const insecureRes = await registerAteneaServiceWorker({
      isProd: true,
      isSecureContext: false,
      navigatorObj: fakeNavigator,
    })
    expect(insecureRes).toBeNull()
    expect(registerSpy).not.toHaveBeenCalled()

    // Registered in production HTTPS / localhost context
    const prodRes = await registerAteneaServiceWorker({
      isProd: true,
      isSecureContext: true,
      navigatorObj: fakeNavigator,
    })
    expect(prodRes).not.toBeNull()
    expect(registerSpy).toHaveBeenCalledWith('/sw.js', {
      scope: '/',
      updateViaCache: 'none',
    })

    // Returns null gracefully if serviceWorker API is absent
    const missingSwRes = await registerAteneaServiceWorker({
      isProd: true,
      isSecureContext: true,
      navigatorObj: {},
    })
    expect(missingSwRes).toBeNull()

    // Returns null gracefully if registration rejects
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    const failingRes = await registerAteneaServiceWorker({
      isProd: true,
      isSecureContext: true,
      navigatorObj: {
        serviceWorker: {
          register: vi.fn().mockRejectedValue(new Error('SW blocked')),
        },
      },
    })
    expect(failingRes).toBeNull()
    expect(warnSpy).toHaveBeenCalledOnce()
  })
})
