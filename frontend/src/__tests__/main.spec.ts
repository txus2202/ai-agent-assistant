import { describe, it, expect, vi } from 'vitest'
import App from '../App.vue'
import router from '../router'

const { mockCreateApp, mockUse, mockMount } = vi.hoisted(() => {
  const mockMount = vi.fn()
  const mockUse = vi.fn().mockReturnThis()
  const mockApp = {
    use: mockUse,
    mount: mockMount
  }
  const mockCreateApp = vi.fn(() => mockApp)
  return { mockApp, mockCreateApp, mockUse, mockMount }
})

vi.mock('vue', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue')>()
  return {
    ...actual,
    createApp: mockCreateApp
  }
})

describe('main.ts bootstrap', () => {
  it('creates Vue application with Pinia, Router, and mounts to #app', async () => {
    document.body.innerHTML = '<div id="app"></div>'

    await import('../main')

    expect(mockCreateApp).toHaveBeenCalledWith(App)
    expect(mockUse).toHaveBeenCalledWith(router)
    expect(mockMount).toHaveBeenCalledWith('#app')
  })
})
