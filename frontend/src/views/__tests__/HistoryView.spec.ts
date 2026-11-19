import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import HistoryView from '../HistoryView.vue'
import { createRouter, createWebHistory } from 'vue-router'
import { createPinia } from 'pinia'
import { useDebateStore } from '../../stores/debate'
import { historyService, type ListDebatesParams } from '../../services/historyService'

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
    vi.spyOn(historyService, 'listDebates').mockImplementation(() => new Promise(() => {}))
    const wrapper = mount(HistoryView, {
      global: { plugins: [router, createPinia()] }
    })
    expect(wrapper.find('.animate-spin').exists()).toBe(true)
  })

  it('renders debates when loaded', async () => {
    const mockDebates = [
      { id: '123', created_at: '2023-10-01T12:00:00Z', events: [{ type: 'start', user_request: 'Test prompt' }] }
    ]
    vi.spyOn(historyService, 'listDebates').mockResolvedValue(mockDebates)

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
    vi.spyOn(historyService, 'listDebates').mockResolvedValue(mockDebates)
    const deleteSpy = vi.spyOn(historyService, 'deleteDebate').mockResolvedValue(undefined)
    
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
    expect(deleteSpy).toHaveBeenCalledWith('123')
    expect(wrapper.text()).not.toContain('Session 123')
  })

  it('restores a debate on click', async () => {
    const mockDebates = [
      { id: '123', created_at: '2023-10-01T12:00:00Z', events: [{ type: 'start', user_request: 'Test prompt' }] }
    ]
    vi.spyOn(historyService, 'listDebates').mockResolvedValue(mockDebates)

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
    vi.spyOn(historyService, 'listDebates').mockResolvedValue(mockDebates)

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
    vi.spyOn(historyService, 'listDebates').mockResolvedValue([])

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
    vi.spyOn(historyService, 'listDebates').mockResolvedValue(mockDebates)
    const deleteSpy = vi.spyOn(historyService, 'deleteDebate').mockResolvedValue(undefined)
    global.confirm = vi.fn().mockReturnValue(false)

    const wrapper = mount(HistoryView, {
      global: { plugins: [router, createPinia()] }
    })
    await flushPromises()

    const deleteBtn = wrapper.find('button[title="Delete Session"]')
    await deleteBtn.trigger('click')
    await flushPromises()

    expect(global.confirm).toHaveBeenCalled()
    expect(deleteSpy).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('ID: 123')
  })

  it('handles fetch error and delete error gracefully', async () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    const listSpy = vi.spyOn(historyService, 'listDebates').mockRejectedValue(new Error('Fetch debates failed'))

    const wrapper = mount(HistoryView, {
      global: { plugins: [router, createPinia()] }
    })
    await flushPromises()

    expect(consoleErrorSpy).toHaveBeenCalledWith('Failed to fetch debates:', expect.any(Error))
    expect(wrapper.find('.animate-spin').exists()).toBe(false)

    // Now test delete error
    global.confirm = vi.fn().mockReturnValue(true)
    listSpy.mockResolvedValue([{ id: '999', created_at: '2023', events: [] }])
    vi.spyOn(historyService, 'deleteDebate').mockRejectedValue(new Error('Delete debate failed'))

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
    vi.spyOn(historyService, 'listDebates').mockResolvedValue(mockDebates)

    const wrapper = mount(HistoryView, {
      global: { plugins: [router, createPinia()] }
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Dictamen final consolidado.')
    expect(wrapper.text()).toContain('200')
    expect(wrapper.text()).not.toContain('320')
  })

  it('consumes paginated summary DTOs and fetches full debate events on demand when restoring', async () => {
    const pinia = createPinia()
    const store = useDebateStore(pinia)
    const fullDetail = {
      id: 'sum-001',
      created_at: '2026-11-18T12:00:00Z',
      user_request: 'Arquitectura paginada',
      status: 'completed',
      events: [
        { type: 'start', user_request: 'Arquitectura paginada' },
        { type: 'done', role: 'supervisor', content: 'Propuesta detallada completa' }
      ]
    }
    const listSpy = vi.spyOn(historyService, 'listDebates').mockImplementation((params: ListDebatesParams) => {
      if (params.offset === 0) {
        return Promise.resolve({
          total: 2,
          total_all: 2,
          limit: 20,
          offset: 0,
          items: [
            {
              id: 'sum-001',
              created_at: '2026-11-18T12:00:00Z',
              user_request: 'Arquitectura paginada',
              target_agent: 'supervisor',
              status: 'completed',
              event_count: 8,
              total_tokens: 450,
              has_hitl: true,
              conclusion: 'Conclusión resumida',
              agents: ['senior_architect']
            }
          ]
        })
      }
      return Promise.resolve({
        total: 2,
        total_all: 2,
        limit: 20,
        offset: 1,
        items: [
          {
            id: 'sum-002',
            created_at: '2026-11-18T11:00:00Z',
            user_request: 'Segunda página',
            target_agent: 'supervisor',
            status: 'completed',
            event_count: 3,
            total_tokens: 150,
            has_hitl: false,
            conclusion: 'Resumen página 2',
            agents: ['Hermes']
          }
        ]
      })
    })
    const getSpy = vi.spyOn(historyService, 'getDebate').mockResolvedValue(fullDetail)

    const wrapper = mount(HistoryView, {
      global: { plugins: [router, pinia] }
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Arquitectura paginada')
    expect(wrapper.text()).toContain('8 events')
    expect(wrapper.text()).toContain('450')
    expect(wrapper.text()).toContain('Conclusión resumida')
    expect(wrapper.text()).toContain('senior architect')
    expect(wrapper.text()).toContain('Mostrando 1 de 2 sesiones')

    // Trigger scroll near bottom to load next page
    const mainEl = wrapper.find('main')
    Object.defineProperty(mainEl.element, 'scrollHeight', { value: 1000, configurable: true })
    Object.defineProperty(mainEl.element, 'scrollTop', { value: 750, configurable: true })
    Object.defineProperty(mainEl.element, 'clientHeight', { value: 200, configurable: true })
    await mainEl.trigger('scroll')
    await flushPromises()

    expect(listSpy).toHaveBeenCalledWith(expect.objectContaining({ limit: 20, offset: 1, filter: 'all' }))
    expect(wrapper.text()).toContain('Segunda página')

    // Restore lightweight card: must fetch full detail via historyService.getDebate
    const pushSpy = vi.spyOn(router, 'push')
    await wrapper.find('.session-card').trigger('click')
    await flushPromises()

    expect(getSpy).toHaveBeenCalledWith('sum-001')
    expect(store.currentSessionId).toBe('sum-001')
    expect(store.messages.some(m => m.content.includes('Propuesta detallada completa'))).toBe(true)
    expect(pushSpy).toHaveBeenCalledWith('/')
  })
})
