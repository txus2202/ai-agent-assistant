import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import AppHeader from '../AppHeader.vue'

// Mock vue-router
const pushMock = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: pushMock
  })
}))

// Mock lucide-vue-next components
vi.mock('lucide-vue-next', () => ({
  Cpu: { template: '<svg></svg>' },
  Volume2: { template: '<svg></svg>' },
  VolumeX: { template: '<svg></svg>' },
  History: { template: '<svg></svg>' },
  ChevronDown: { template: '<svg></svg>' }
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
    // Mock fetch to prevent ERR_INVALID_URL in jsdom
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([])
    })
  })

  afterEach(() => {
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
    const audioButton = wrapper.find('button[title="Toggle System Audio"]')
    
    // Initial state: Volume2 should be visible
    expect(wrapper.vm.isMuted).toBe(false)
    
    await audioButton.trigger('click')
    
    // After click: isMuted should be true
    expect(wrapper.vm.isMuted).toBe(true)
  })
})
