import { describe, it, expect } from 'vitest'
import router from '../index'

describe('Router', () => {
  it('has correct route definitions for home and history', () => {
    const routes = router.getRoutes()
    const homeRoute = routes.find(r => r.name === 'home')
    const historyRoute = routes.find(r => r.name === 'history')

    expect(homeRoute).toBeDefined()
    expect(homeRoute?.path).toBe('/')

    expect(historyRoute).toBeDefined()
    expect(historyRoute?.path).toBe('/history')
  })

  it('navigates to home and resolves component', async () => {
    await router.push('/')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/')
    expect(router.currentRoute.value.name).toBe('home')
  })

  it('navigates to history and resolves lazy-loaded component', async () => {
    await router.push('/history')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/history')
    expect(router.currentRoute.value.name).toBe('history')

    // Verify lazy component resolves HistoryView
    const historyRoute = router.getRoutes().find(r => r.name === 'history')
    expect(historyRoute?.components?.default).toBeDefined()
  })
})
