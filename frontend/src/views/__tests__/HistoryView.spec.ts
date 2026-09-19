import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import HistoryView from '../HistoryView.vue'
import { createRouter, createWebHistory } from 'vue-router'

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
      global: { plugins: [router] }
    })
    expect(wrapper.find('.animate-spin').exists()).toBe(true)
  })

  it('renders debates when loaded', async () => {
    const mockDebates = [
      { id: '123', created_at: '2023-10-01T12:00:00Z', messages: [{ type: 'start', user_request: 'Test prompt' }] }
    ]
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockDebates)
    })

    const wrapper = mount(HistoryView, {
      global: { plugins: [router] }
    })
    
    await flushPromises()

    expect(wrapper.text()).toContain('Test prompt')
    expect(wrapper.text()).toContain('Session 123')
  })

  it('deletes a debate', async () => {
    const mockDebates = [
      { id: '123', created_at: '2023-10-01T12:00:00Z', messages: [] }
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
      global: { plugins: [router] }
    })
    
    await flushPromises()
    
    const deleteBtn = wrapper.find('button[title="Delete Session"]')
    await deleteBtn.trigger('click')
    await flushPromises()

    expect(global.confirm).toHaveBeenCalled()
    expect(global.fetch).toHaveBeenCalledWith('/api/history/123', { method: 'DELETE' })
    expect(wrapper.text()).not.toContain('Session 123')
  })
})
