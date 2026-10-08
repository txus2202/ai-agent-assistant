import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ParticleOrb from '../ParticleOrb.vue'

describe('ParticleOrb.vue', () => {
  let requestAnimationFrameSpy: any
  let cancelAnimationFrameSpy: any

  beforeEach(() => {
    setActivePinia(createPinia())
    // Mock Canvas API
    HTMLCanvasElement.prototype.getContext = vi.fn(() => ({
      clearRect: vi.fn(),
      beginPath: vi.fn(),
      arc: vi.fn(),
      fill: vi.fn(),
      createRadialGradient: vi.fn(() => ({
        addColorStop: vi.fn()
      })),
      createLinearGradient: vi.fn(() => ({
        addColorStop: vi.fn()
      })),
      fillRect: vi.fn(),
      moveTo: vi.fn(),
      lineTo: vi.fn(),
      stroke: vi.fn(),
    })) as any

    requestAnimationFrameSpy = vi.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => {
      return 1 // return dummy id
    })
    cancelAnimationFrameSpy = vi.spyOn(window, 'cancelAnimationFrame')
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('mounts properly and starts animation loop', () => {
    const wrapper = mount(ParticleOrb, {
      props: {
        isDebating: false,
        activeAgentColor: '#ffffff'
      }
    })
    
    expect(wrapper.exists()).toBe(true)
    expect(requestAnimationFrameSpy).toHaveBeenCalled()
  })

  it('cancels animation frame on unmount', () => {
    const wrapper = mount(ParticleOrb, {
      props: {
        isDebating: false,
        activeAgentColor: '#ffffff'
      }
    })
    
    wrapper.unmount()
    expect(cancelAnimationFrameSpy).toHaveBeenCalled()
  })

  it('renders audio UI elements structurally', () => {
    const wrapper = mount(ParticleOrb, {
      props: {
        isDebating: false,
        activeAgentColor: '#ffffff'
      }
    })
    
    // Check if the waveform canvas exists
    const waveformCanvas = wrapper.find('#waveformCanvas')
    expect(waveformCanvas.exists()).toBe(true)

    // Check if the microphone button exists
    const micButton = wrapper.find('#micButton')
    expect(micButton.exists()).toBe(true)
  })
  
  it('updates correctly when props change', async () => {
    const wrapper = mount(ParticleOrb, {
      props: {
        isDebating: false,
        activeAgentColor: '#ffffff'
      }
    })
    
    await wrapper.setProps({
      isDebating: true,
      activeAgentColor: '#00e5ff' // Cyan
    })
    
    expect(wrapper.props('isDebating')).toBe(true)
    expect(wrapper.props('activeAgentColor')).toBe('#00e5ff')
  })

  it('displays correct voice state text when auto listen is enabled', async () => {
    const wrapper = mount(ParticleOrb, {
      props: { isDebating: false, activeAgentColor: '#ffffff' }
    })
    
    // Default
    expect(wrapper.text()).toContain('ESTADO VOZ: EN REPOSO')
    
    // Need to use the store to change state
    const { useDebateStore } = await import('../../stores/debate')
    const store = useDebateStore()
    
    store.isAutoListenEnabled = true
    await wrapper.vm.$nextTick()
    
    expect(wrapper.text()).toContain('ESTADO VOZ: ESPERANDO WAKE WORD')
  })
})
