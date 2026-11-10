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

  it('redirects to /setup when system is not initialized', async () => {
    const authStore = useAuthStore()
    authStore.isInitialized = false
    authStore.user = null

    await router.push('/')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/setup')
  })

  it('redirects unauthenticated user to /login when system is initialized', async () => {
    const authStore = useAuthStore()
    authStore.isInitialized = true
    authStore.user = null

    await router.push('/')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/login')
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

  it('redirects away from /setup to /login if system is already initialized and unauthenticated', async () => {
    const authStore = useAuthStore()
    authStore.isInitialized = true
    authStore.user = null

    await router.push('/setup')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/login')
  })
})
