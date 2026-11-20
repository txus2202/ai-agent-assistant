import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import App from '../App.vue'
import router from '../router'
import { httpClient } from '../services/httpClient'
import { useAuthStore } from '../stores/auth'

const { mockCreateApp, mockUse, mockMount } = vi.hoisted(() => {
  const mockMount = vi.fn()
  const mockUse = vi.fn().mockReturnThis()
  const mockApp = {
    use: mockUse,
    mount: mockMount,
  }
  const mockCreateApp = vi.fn(() => mockApp)
  return { mockApp, mockCreateApp, mockUse, mockMount }
})

vi.mock('vue', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue')>()
  return {
    ...actual,
    createApp: mockCreateApp,
  }
})

describe('main.ts bootstrap', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('creates Vue application, configures httpClient without monkey-patching window.fetch, and mounts #app', async () => {
    const fetchBefore = window.fetch
    const configureSpy = vi.spyOn(httpClient, 'configure')
    document.body.innerHTML = '<div id="app"></div>'

    await import('../main')

    expect(mockCreateApp).toHaveBeenCalledWith(App)
    expect(mockUse).toHaveBeenCalledWith(router)
    expect(mockMount).toHaveBeenCalledWith('#app')
    expect(window.fetch).toBe(fetchBefore)
    expect(configureSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        onUnauthorized: expect.any(Function),
      }),
    )

    const onUnauthorized = configureSpy.mock.calls[0]?.[0]?.onUnauthorized
    expect(onUnauthorized).toBeTypeOf('function')

    const authStore = useAuthStore()
    authStore.user = {
      id: 'u1',
      username: 'admin',
      is_admin: true,
      is_active: true,
      created_at: '2026-11-09T00:00:00Z',
    }
    const pushSpy = vi.spyOn(router, 'push').mockResolvedValue(undefined)
    await router.replace('/history')

    onUnauthorized?.({ url: '/api/config/agents', status: 401 })

    expect(authStore.user).toBeNull()
    expect(pushSpy).toHaveBeenCalledWith({
      path: '/login',
      query: { redirect: '/history' },
    })
  })
})
