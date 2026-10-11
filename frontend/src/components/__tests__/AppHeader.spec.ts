import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import AppHeader from '../AppHeader.vue'
import { useDebateStore } from '../../stores/debate'

// Mock vue-router
const pushMock = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: pushMock
  })
}))

// Mock @lucide/vue components
vi.mock('@lucide/vue', () => ({
  Cpu: { template: '<svg></svg>' },
  Volume2: { template: '<svg></svg>' },
  VolumeX: { template: '<svg></svg>' },
  History: { template: '<svg></svg>' },
  ChevronDown: { template: '<svg></svg>' },
  Ear: { template: '<svg></svg>' },
  EarOff: { template: '<svg></svg>' }
}))

// Mock configStore
vi.mock('../../stores/config', () => ({
  useConfigStore: () => ({
    providers: [
      { id: 'gemini', name: 'Gemini', models: [{ id: 'gemini-1.5-pro', name: 'Gemini Pro 1.5' }] }
    ]
  })
}))

describe('AppHeader.vue', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    // Mock fetch to prevent ERR_INVALID_URL in jsdom
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([])
    })
  })

  afterEach(async () => {
    await flushPromises()
    vi.restoreAllMocks()
  })

  it('renders correctly with version', () => {
    const wrapper = mount(AppHeader)
    expect(wrapper.text()).toContain('System Core v')
    expect(wrapper.text()).toContain('A.T.E.N.E.A.')
    expect(wrapper.text()).toContain('SUPERVISOR: GEMINI - PRO 1.5')
  })

  it('navigates to history on button click', async () => {
    const wrapper = mount(AppHeader)
    const historyButton = wrapper.find('button[title="Debate History"]')
    await historyButton.trigger('click')
    expect(pushMock).toHaveBeenCalledWith('/history')
  })


  it('toggles audio on button click', async () => {
    const wrapper = mount(AppHeader)
    const store = useDebateStore()
    const audioButton = wrapper.find('button[title="Toggle System Audio"]')
    
    // Initial state: Voice output is enabled by default
    expect(store.isVoiceOutputEnabled).toBe(true)
    
    await audioButton.trigger('click')
    
    // After click: Voice output should be disabled
    expect(store.isVoiceOutputEnabled).toBe(false)
  })

  it('toggles auto-listen on button click', async () => {
    const wrapper = mount(AppHeader)
    const store = useDebateStore()
    const autoListenButton = wrapper.find('button[title="Toggle Auto-Listen (Wake Word)"]')
    
    expect(store.isAutoListenEnabled).toBe(false)
    
    // In our component, we mock startAutoListen to avoid WebSocket connections
    store.startAutoListen = vi.fn().mockImplementation(() => { store.isAutoListenEnabled = true })
    store.stopAutoListen = vi.fn().mockImplementation(() => { store.isAutoListenEnabled = false })
    
    await autoListenButton.trigger('click')
    
    expect(store.startAutoListen).toHaveBeenCalled()
    expect(store.isAutoListenEnabled).toBe(true)
    
    await autoListenButton.trigger('click')
    expect(store.stopAutoListen).toHaveBeenCalled()
    expect(store.isAutoListenEnabled).toBe(false)
  })

  it('loads supervisor configuration from backend on mount', async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === '/api/config/agents/supervisor') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ provider: 'Anthropic', model_name: 'Claude 3.5 Sonnet' })
        })
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve([]) })
    })

    const wrapper = mount(AppHeader)
    await flushPromises()

    expect(wrapper.text()).toContain('SUPERVISOR: Anthropic - Claude 3.5 Sonnet')
  })

  it('handles supervisor dropdown navigation, back button, and model selection with persistence', async () => {
    const wrapper = mount(AppHeader)
    await flushPromises()

    const supervisorBtn = wrapper.findAll('button').find(b => b.text().includes('SUPERVISOR:'))
    expect(supervisorBtn).toBeDefined()

    // 1. Open dropdown
    await supervisorBtn!.trigger('click')
    expect(wrapper.text()).toContain('Select Provider')

    // 2. Select Gemini provider
    const providerBtn = wrapper.findAll('button').find(b => b.text().includes('Gemini'))
    expect(providerBtn).toBeDefined()
    await providerBtn!.trigger('click')

    // Should now show provider's models and back button
    expect(wrapper.text()).toContain('Gemini Pro 1.5')
    const backBtn = wrapper.findAll('button').find(b => b.text().includes('< BACK'))
    expect(backBtn).toBeDefined()

    // Click back button to return to provider view
    await backBtn!.trigger('click')
    expect(wrapper.text()).toContain('Select Provider')

    // Re-select provider and select model
    const reProviderBtn = wrapper.findAll('button').find(b => b.text().includes('Gemini'))
    await reProviderBtn!.trigger('click')

    const modelBtn = wrapper.findAll('button').find(b => b.text().includes('Gemini Pro 1.5'))
    expect(modelBtn).toBeDefined()

    await modelBtn!.trigger('click')

    // Should close dropdown, update display and send PUT request
    expect(wrapper.text()).not.toContain('Select Provider')
    expect(wrapper.text()).toContain('SUPERVISOR: Gemini - Gemini Pro 1.5')
    expect(global.fetch).toHaveBeenCalledWith('/api/config/agents/supervisor', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider: 'Gemini', model_name: 'Gemini Pro 1.5' })
    })
  })

  it('closes dropdown and resets selected provider on click outside or toggle', async () => {
    const wrapper = mount(AppHeader, {
      attachTo: document.body
    })
    await flushPromises()

    const supervisorBtn = wrapper.findAll('button').find(b => b.text().includes('SUPERVISOR:'))
    await supervisorBtn!.trigger('click')
    expect(wrapper.text()).toContain('Select Provider')

    // Click outside
    document.dispatchEvent(new MouseEvent('click'))
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).not.toContain('Select Provider')

    // Open and toggle close
    await supervisorBtn!.trigger('click')
    expect(wrapper.text()).toContain('Select Provider')
    await supervisorBtn!.trigger('click')
    expect(wrapper.text()).not.toContain('Select Provider')

    wrapper.unmount()
  })

  it('handles backend errors gracefully when loading or saving supervisor config', async () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    global.fetch = vi.fn().mockRejectedValue(new Error('Supervisor API offline'))

    const wrapper = mount(AppHeader)
    await flushPromises()

    expect(consoleErrorSpy).toHaveBeenCalledWith('Error fetching supervisor config:', expect.any(Error))

    const supervisorBtn = wrapper.findAll('button').find(b => b.text().includes('SUPERVISOR:'))
    await supervisorBtn!.trigger('click')

    const providerBtn = wrapper.findAll('button').find(b => b.text().includes('Gemini'))
    await providerBtn!.trigger('click')

    const modelBtn = wrapper.findAll('button').find(b => b.text().includes('Gemini Pro 1.5'))
    await modelBtn!.trigger('click')
    await flushPromises()

    expect(consoleErrorSpy).toHaveBeenCalledWith('Failed to save supervisor config:', expect.any(Error))
  })
})
