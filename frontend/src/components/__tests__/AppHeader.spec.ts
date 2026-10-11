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
})
