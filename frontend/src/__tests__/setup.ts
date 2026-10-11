import { vi } from 'vitest'

// Polyfill unimplemented HTMLMediaElement methods in JSDOM to prevent stderr warnings
if (typeof window !== 'undefined' && window.HTMLMediaElement) {
  window.HTMLMediaElement.prototype.play = vi.fn().mockResolvedValue(undefined)
  window.HTMLMediaElement.prototype.pause = vi.fn()
  window.HTMLMediaElement.prototype.load = vi.fn()
}
