export interface ServiceWorkerRegistrationLike {
  update?: () => Promise<unknown>
}

export interface NavigatorServiceWorkerLike {
  serviceWorker?: {
    register: (
      scriptURL: string,
      options?: { scope?: string; updateViaCache?: 'all' | 'imports' | 'none' },
    ) => Promise<ServiceWorkerRegistrationLike>
  }
}

export interface RegisterSwOptions {
  isProd?: boolean
  isSecureContext?: boolean
  navigatorObj?: NavigatorServiceWorkerLike
}

/**
 * Registers the ATENEA App-Shell Service Worker exclusively in production secure contexts.
 * Skipped during Vite dev HMR and automated test runs so route mocks remain deterministic.
 */
export async function registerAteneaServiceWorker(
  options: RegisterSwOptions = {},
): Promise<ServiceWorkerRegistrationLike | null> {
  const isProd = options.isProd ?? import.meta.env.PROD
  if (!isProd) {
    return null
  }

  const secure =
    options.isSecureContext ?? (typeof window !== 'undefined' && Boolean(window.isSecureContext))
  if (!secure) {
    return null
  }

  const nav =
    options.navigatorObj ??
    (typeof navigator !== 'undefined' ? (navigator as unknown as NavigatorServiceWorkerLike) : undefined)
  if (!nav?.serviceWorker || typeof nav.serviceWorker.register !== 'function') {
    return null
  }

  try {
    return await nav.serviceWorker.register('/sw.js', {
      scope: '/',
      updateViaCache: 'none',
    })
  } catch (error) {
    console.warn('ATENEA Service Worker registration skipped:', error)
    return null
  }
}

