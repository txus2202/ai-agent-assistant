import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import router from '../index'
import { useAuthStore } from '../../stores/auth'

describe('Router & Navigation Guards', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('has correct route definitions', () => {
    const routes = router.getRoutes()
    expect(routes.find(r => r.name === 'home')).toBeDefined()
    expect(routes.find(r => r.name === 'history')).toBeDefined()
    expect(routes.find(r => r.name === 'login')).toBeDefined()
    expect(routes.find(r => r.name === 'setup')).toBeDefined()
  })

  it.each([
    {
      description: 'redirects to /setup when system is not initialized',
      isInitialized: false,
      targetPath: '/',
      expectedPath: '/setup',
    },
    {
      description: 'redirects unauthenticated user to /login when system is initialized',
      isInitialized: true,
      targetPath: '/',
      expectedPath: '/login',
    },
    {
      description: 'redirects away from /setup to /login if system is already initialized and unauthenticated',
      isInitialized: true,
      targetPath: '/setup',
      expectedPath: '/login',
    },
  ])('$description', async ({ isInitialized, targetPath, expectedPath }) => {
    const authStore = useAuthStore()
    authStore.isInitialized = isInitialized
    authStore.user = null

    await router.push(targetPath)
    await router.isReady()

    expect(router.currentRoute.value.path).toBe(expectedPath)
  })

  it('does not redirect to /setup when backend is unavailable', async () => {
    const authStore = useAuthStore()
    authStore.isBackendAvailable = false
    authStore.isInitialized = null
    authStore.user = null

    await router.push('/')
    await router.isReady()

    expect(router.currentRoute.value.path).not.toBe('/setup')
  })

  it('redirects to /login with redirect query when trying to access /history while unauthenticated', async () => {
    const authStore = useAuthStore()
    authStore.isInitialized = true
    authStore.user = null

    await router.push('/history')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/login')
    expect(router.currentRoute.value.query.redirect).toBe('/history')
  })

  it('allows authenticated user to access protected routes', async () => {
    const authStore = useAuthStore()
    authStore.isInitialized = true
    authStore.user = {
      id: 'usr-1',
      username: 'admin',
      is_admin: true,
      is_active: true,
      created_at: '2026-11-09T00:00:00'
    }

    await router.push('/')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/')

    await router.push('/history')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/history')
  })

  it('redirects authenticated user away from /login to /', async () => {
    const authStore = useAuthStore()
    authStore.isInitialized = true
    authStore.user = {
      id: 'usr-1',
      username: 'admin',
      is_admin: true,
      is_active: true,
      created_at: '2026-11-09T00:00:00'
    }

    await router.push('/login')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/')
  })

  it('redirects unknown routes to /login and logs out user when router error occurs', async () => {
    const authStore = useAuthStore()
    authStore.isInitialized = true
    authStore.user = {
      id: 'usr-1',
      username: 'admin',
      is_admin: true,
      is_active: true,
      created_at: '2026-11-09T00:00:00'
    }
    const logoutSpy = vi.spyOn(authStore, 'logout').mockImplementation(async () => {
      authStore.user = null
    })

    await router.push('/non-existent-route-xyz')
    await router.isReady()

    expect(logoutSpy).toHaveBeenCalled()
    expect(authStore.user).toBeNull()
    expect(router.currentRoute.value.path).toBe('/login')
  })
})
