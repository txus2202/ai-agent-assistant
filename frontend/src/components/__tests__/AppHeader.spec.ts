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
  Cpu: { template: '<svg data-test="cpu-icon"></svg>' },
  Volume2: { template: '<svg data-test="volume-on"></svg>' },
  VolumeX: { template: '<svg data-test="volume-off"></svg>' },
  History: { template: '<svg data-test="history-icon"></svg>' },
  Ear: { template: '<svg data-test="ear-on"></svg>' },
  EarOff: { template: '<svg data-test="ear-off"></svg>' },
  Sun: { template: '<svg data-test="sun-icon"></svg>' },
  Moon: { template: '<svg data-test="moon-icon"></svg>' }
}))

describe('AppHeader.vue', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(async () => {
    await flushPromises()
    vi.restoreAllMocks()
  })

  it('renders correctly with version and without supervisor info', () => {
    const wrapper = mount(AppHeader)
    expect(wrapper.text().toUpperCase()).toContain('SYSTEM CORE V')
    expect(wrapper.text()).toContain('A.T.E.N.E.A.')
    expect(wrapper.text()).not.toContain('SUPERVISOR:')
  })

  it('renders dynamic project_name and project_description from debate store topology', async () => {
    const store = useDebateStore()
    store.topology = {
      project_name: 'TITAN-CORE',
      project_description: 'Plataforma de Inteligencia Artificial Distribuida',
      supervisor: 'Atenea',
      interpreters: [],
      proposers: [],
      reviewers: [],
      evaluators: [],
      implementers: []
    }

    const wrapper = mount(AppHeader)
    expect(wrapper.text()).toContain('TITAN-CORE')
    expect(wrapper.text()).toContain('Plataforma de Inteligencia Artificial Distribuida')
  })

  it('renders theme toggle button on the right and toggles dark/light mode', async () => {
    const wrapper = mount(AppHeader)
    const toggleBtn = wrapper.find('[data-test="theme-toggle-btn"]')
    expect(toggleBtn.exists()).toBe(true)
    
    // Initial state is dark mode (shows moon)
    expect(wrapper.find('[data-test="moon-icon"]').exists()).toBe(true)

    // Click to toggle to light mode
    await toggleBtn.trigger('click')
    expect(wrapper.find('[data-test="sun-icon"]').exists()).toBe(true)

    // Click again to toggle back to dark mode
    await toggleBtn.trigger('click')
    expect(wrapper.find('[data-test="moon-icon"]').exists()).toBe(true)
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

  it('applies desktop active styling to speaker button when voice output is enabled', () => {
    const wrapper = mount(AppHeader)
    const store = useDebateStore()
    store.isVoiceOutputEnabled = true
    const audioButton = wrapper.find('button[title="Toggle System Audio"]')
    expect(audioButton.classes()).toContain('xl:text-amber-400')
    expect(audioButton.classes()).toContain('xl:bg-amber-900/30')
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

  it('shares matching amber hover and active color schemes between speaker, auto-listen, and history buttons', async () => {
    const wrapper = mount(AppHeader)
    const store = useDebateStore()
    store.isVoiceOutputEnabled = true
    store.isAutoListenEnabled = true
    await wrapper.vm.$nextTick()

    const speakerBtn = wrapper.find('button[title="Toggle System Audio"]')
    const autoListenBtn = wrapper.find('button[title="Toggle Auto-Listen (Wake Word)"]')
    const historyBtn = wrapper.find('button[title="Debate History"]')

    // Both active buttons share amber active background and text
    expect(speakerBtn.classes()).toContain('text-amber-600')
    expect(speakerBtn.classes()).toContain('bg-amber-500/15')
    expect(autoListenBtn.classes()).toContain('text-amber-600')
    expect(autoListenBtn.classes()).toContain('bg-amber-500/15')

    // History button shares the same hover amber styling
    expect(historyBtn.classes()).toContain('hover:text-amber-600')
    expect(historyBtn.classes()).toContain('hover:border-amber-500/40')
  })
})
