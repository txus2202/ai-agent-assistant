/**
 * Resolves WebSocket URL dynamically to support local Vite `/ws` proxy,
 * Nginx HTTPS/WSS termination, explicit `VITE_WS_URL`, and Tailscale hosts.
 */
export function resolveWsUrl(path: string): string {
  const configured = import.meta.env.VITE_WS_URL?.trim()
  if (configured) {
    try {
      const parsed = new URL(configured)
      return `${parsed.origin}${path}`
    } catch {
      return configured.replace(/\/ws\/debate\/?$/, '') + path
    }
  }
  if (typeof window !== 'undefined' && window.location?.host) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${protocol}//${window.location.host}${path}`
  }
  return `ws://localhost:8000${path}`
}

