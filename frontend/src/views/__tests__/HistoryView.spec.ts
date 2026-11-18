import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import HistoryView from '../HistoryView.vue'
import { createRouter, createWebHistory } from 'vue-router'
import { createPinia } from 'pinia'
import { useDebateStore } from '../../stores/debate'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: { template: '<div>Home</div>' } },
    { path: '/history', name: 'history', component: HistoryView }
  ]
})

describe('HistoryView.vue', () => {
  beforeEach(async () => {
    router.push('/history')
    await router.isReady()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders loading state initially', () => {
    global.fetch = vi.fn().mockImplementation(() => new Promise(() => {}))
    const wrapper = mount(HistoryView, {
      global: { plugins: [router, createPinia()] }
    })
    expect(wrapper.find('.animate-spin').exists()).toBe(true)
  })

  it('renders debates when loaded', async () => {
    const mockDebates = [
      { id: '123', created_at: '2023-10-01T12:00:00Z', events: [{ type: 'start', user_request: 'Test prompt' }] }
    ]
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockDebates)
    })

    const wrapper = mount(HistoryView, {
      global: { plugins: [router, createPinia()] }
    })
    
    await flushPromises()

    expect(wrapper.text()).toContain('Test prompt')
    expect(wrapper.text()).toContain('ID: 123')
  })

  it('deletes a debate', async () => {
    const mockDebates = [
      { id: '123', created_at: '2023-10-01T12:00:00Z', events: [] }
    ]
    global.fetch = vi.fn().mockImplementation((url, options) => {
      if (options?.method === 'DELETE') {
        return Promise.resolve({ ok: true })
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockDebates)
      })
    })
    
    // Mock window.confirm
    global.confirm = vi.fn().mockReturnValue(true)

    const wrapper = mount(HistoryView, {
      global: { plugins: [router, createPinia()] }
    })
    
    await flushPromises()
    
    const deleteBtn = wrapper.find('button[title="Delete Session"]')
    await deleteBtn.trigger('click')
    await flushPromises()

    expect(global.confirm).toHaveBeenCalled()
    expect(global.fetch).toHaveBeenCalledWith('/api/debates/123', { method: 'DELETE' })
    expect(wrapper.text()).not.toContain('Session 123')
  })

  it('restores a debate on click', async () => {
    const mockDebates = [
      { id: '123', created_at: '2023-10-01T12:00:00Z', events: [{ type: 'start', user_request: 'Test prompt' }] }
    ]
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockDebates)
    })

    const wrapper = mount(HistoryView, {
      global: { plugins: [router, createPinia()] }
    })
    await flushPromises()

    const cardBtn = wrapper.find('.session-card')
    expect(cardBtn.exists()).toBe(true)
    expect(cardBtn.element.tagName).toBe('BUTTON')

    const pushSpy = vi.spyOn(router, 'push')
    await cardBtn.trigger('click')
    expect(pushSpy).toHaveBeenCalledWith('/')
  })

  it('restores debate from history with HITL closed even if debate has hitl_required event', async () => {
    const pinia = createPinia()
    const store = useDebateStore(pinia)
    const mockDebates = [
      {
        id: 'hitl-session-1',
        created_at: '2023-10-01T12:00:00Z',
        events: [
          {
            type: 'hitl_required',
            role: 'devops_secops',
            content: 'Acción requerida',
            metadata: { checkpoint: 'after_devops_secops' }
          }
        ]
      }
    ]
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockDebates)
    })

    const wrapper = mount(HistoryView, {
      global: { plugins: [router, pinia] }
    })
    await flushPromises()

    const cardBtn = wrapper.find('.session-card')
    await cardBtn.trigger('click')

    expect(store.currentSessionId).toBe('hitl-session-1')
    expect(store.isHitlRequired).toBe(false)
    expect(store.hitlCheckpoint).toBeNull()
  })

  it('navigates back to home on back button click', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([])
    })

    const wrapper = mount(HistoryView, {
      global: { plugins: [router, createPinia()] }
    })
    await flushPromises()

    const pushSpy = vi.spyOn(router, 'push')
    const backBtn = wrapper.find('header button')
    await backBtn.trigger('click')
    expect(pushSpy).toHaveBeenCalledWith('/')
  })

  it('does not delete debate if user cancels confirmation', async () => {
    const mockDebates = [{ id: '123', created_at: '2023-10-01T12:00:00Z', events: [] }]
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockDebates)
    })
    global.confirm = vi.fn().mockReturnValue(false)

    const wrapper = mount(HistoryView, {
      global: { plugins: [router, createPinia()] }
    })
    await flushPromises()

    const deleteBtn = wrapper.find('button[title="Delete Session"]')
    await deleteBtn.trigger('click')
    await flushPromises()

    expect(global.confirm).toHaveBeenCalled()
    expect(global.fetch).not.toHaveBeenCalledWith('/api/debates/123', { method: 'DELETE' })
    expect(wrapper.text()).toContain('ID: 123')
  })

  it('handles fetch error and delete error gracefully', async () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    global.fetch = vi.fn().mockRejectedValue(new Error('Fetch debates failed'))

    const wrapper = mount(HistoryView, {
      global: { plugins: [router, createPinia()] }
    })
    await flushPromises()

    expect(consoleErrorSpy).toHaveBeenCalledWith('Failed to fetch debates:', expect.any(Error))
    expect(wrapper.find('.animate-spin').exists()).toBe(false)

    // Now test delete error
    global.confirm = vi.fn().mockReturnValue(true)
    global.fetch = vi.fn().mockImplementation((url, opts) => {
      if (opts?.method === 'DELETE') {
        return Promise.reject(new Error('Delete debate failed'))
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve([{ id: '999', created_at: '2023', events: [] }]) })
    })

    const wrapper2 = mount(HistoryView, {
      global: { plugins: [router, createPinia()] }
    })
    await flushPromises()

    const deleteBtn = wrapper2.find('button[title="Delete Session"]')
    await deleteBtn.trigger('click')
    await flushPromises()

    expect(consoleErrorSpy).toHaveBeenCalledWith('Failed to delete debate:', expect.any(Error))
  })

  it('extracts done conclusions, detects hitl_required badges, and avoids token double counting', async () => {
    const mockDebates = [
      {
        id: 'deb-metrics',
        created_at: '2026-11-18T12:00:00Z',
        user_request: 'Revisión de arquitectura',
        events: [
          { type: 'start', user_request: 'Revisión de arquitectura' },
          { type: 'hitl_required', role: 'Hermes', content: 'Aprobar alcance' },
          { type: 'agent_completed', role: 'Hermes', content: 'Alcance ok', metadata: { total_tokens: '120', tokens: '120' } },
          { type: 'done', role: 'Hermes', content: 'Alcance ok', metadata: { metrics_reported: 'true' } },
          { type: 'done', role: 'Atenea', content: 'Dictamen final consolidado.', metadata: { total_tokens: '80', tokens: '80' } },
        ]
      }
    ]
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockDebates)
    })

    const wrapper = mount(HistoryView, {
      global: { plugins: [router, createPinia()] }
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Dictamen final consolidado.')
    expect(wrapper.text()).toContain('200')
    expect(wrapper.text()).not.toContain('320')
  })
})
