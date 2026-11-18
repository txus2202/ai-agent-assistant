import { describe, it, expect, vi, beforeEach, afterEach, type MockInstance } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ParticleOrb from '../ParticleOrb.vue'
import { useDebateStore } from '../../stores/debate'

describe('ParticleOrb.vue', () => {
  let requestAnimationFrameSpy: MockInstance<typeof window.requestAnimationFrame>
  let cancelAnimationFrameSpy: MockInstance<typeof window.cancelAnimationFrame>
  let mockStream: MediaStream
  let mockTrackStop: ReturnType<typeof vi.fn>
  let createdRecorders: MockMediaRecorder[]

  class MockMediaRecorder {
    ondataavailable: ((e: { data: Blob }) => void) | null = null
    onstop: (() => void) | null = null
    state = 'inactive'
    stream: MediaStream

    constructor(stream: MediaStream) {
      this.stream = stream
      createdRecorders.push(this)
    }

    start() {
      this.state = 'recording'
    }

    stop() {
      this.state = 'inactive'
      if (this.onstop) this.onstop()
    }
  }

  class MockAudioContext {
    state = 'running'
    createAnalyser() {
      return {
        minDecibels: -70,
        smoothingTimeConstant: 0.2,
        fftSize: 256,
        frequencyBinCount: 128,
        connect: vi.fn(),
        disconnect: vi.fn(),
        getByteFrequencyData: vi.fn((arr: Uint8Array) => {
          arr.fill(0) // silence by default
        }),
        getByteTimeDomainData: vi.fn((arr: Uint8Array) => {
          arr.fill(128)
        })
      }
    }
    createMediaStreamSource() {
      return {
        connect: vi.fn(),
        disconnect: vi.fn()
      }
    }
    close() {
      return Promise.resolve()
    }
  }

  beforeEach(() => {
    setActivePinia(createPinia())
    createdRecorders = []
    mockTrackStop = vi.fn()
    mockStream = {
      getTracks: () => [{ stop: mockTrackStop }]
    } as unknown as MediaStream

    // Mock Canvas API
    HTMLCanvasElement.prototype.getContext = vi.fn(() => ({
      clearRect: vi.fn(),
      beginPath: vi.fn(),
      arc: vi.fn(),
      fill: vi.fn(),
      stroke: vi.fn(),
      moveTo: vi.fn(),
      lineTo: vi.fn(),
      createRadialGradient: vi.fn(() => ({ addColorStop: vi.fn() })),
      createLinearGradient: vi.fn(() => ({ addColorStop: vi.fn() })),
      fillRect: vi.fn(),
      lineWidth: 1,
      strokeStyle: '',
      fillStyle: ''
    })) as unknown as HTMLCanvasElement['getContext']

    window.requestAnimationFrame = vi.fn().mockImplementation(() => 1)
    window.cancelAnimationFrame = vi.fn()
    requestAnimationFrameSpy = vi.spyOn(window, 'requestAnimationFrame')
    cancelAnimationFrameSpy = vi.spyOn(window, 'cancelAnimationFrame')

    // Mock mediaDevices
    Object.defineProperty(navigator, 'mediaDevices', {
      value: {
        getUserMedia: vi.fn().mockResolvedValue(mockStream)
      },
      configurable: true,
      writable: true
    })

    vi.stubGlobal('MediaRecorder', MockMediaRecorder)
    vi.stubGlobal('AudioContext', MockAudioContext)
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ text: 'Transcripción exitosa' })
    }))
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
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
    
    const waveformCanvas = wrapper.find('#waveformCanvas')
    expect(waveformCanvas.exists()).toBe(true)

    const micButton = wrapper.find('#micButton')
    expect(micButton.exists()).toBe(true)
  })
  
  it('updates correctly when props change and handles 3-char hex colors', async () => {
    const wrapper = mount(ParticleOrb, {
      props: {
        isDebating: false,
        activeAgentColor: '#fff',
        activeAgentIndex: 1
      }
    })
    
    await wrapper.setProps({
      isDebating: true,
      activeAgentColor: '#00e5ff',
      activeAgentIndex: 2
    })
    
    expect(wrapper.props('isDebating')).toBe(true)
    expect(wrapper.props('activeAgentColor')).toBe('#00e5ff')
    expect(wrapper.props('activeAgentIndex')).toBe(2)
  })

  it('toggles recording on click, processes audio blob, and submits draft message', async () => {
    const store = useDebateStore()
    const stopTtsSpy = vi.spyOn(store, 'stopTts')
    const unlockSpy = vi.spyOn(store, 'unlockAudioContext')

    const wrapper = mount(ParticleOrb, {
      props: {
        isDebating: false,
        activeAgentColor: '#00e5ff'
      }
    })

    const micButton = wrapper.find('#micButton')
    
    // Start recording
    await micButton.trigger('click')
    await flushPromises()

    expect(stopTtsSpy).toHaveBeenCalled()
    expect(unlockSpy).toHaveBeenCalled()
    expect(store.isRecording).toBe(true)
    expect(wrapper.text()).toContain('ESCUCHANDO...')
    expect(wrapper.text()).toContain('ESTADO VOZ: ESCUCHANDO ORDEN')

    const recorder = createdRecorders[0]
    expect(recorder).toBeDefined()
    expect(recorder!.state).toBe('recording')

    // Simulate incoming audio chunk
    recorder!.ondataavailable!({ data: new Blob(['audio-data'], { type: 'audio/webm' }) })

    // Stop recording by clicking button again
    await micButton.trigger('click')
    await flushPromises()

    expect(store.isRecording).toBe(false)
    expect(mockTrackStop).toHaveBeenCalled()
    expect(global.fetch).toHaveBeenCalledWith('/api/audio/transcribe', expect.objectContaining({
      method: 'POST'
    }))
    expect(store.draftMessage).toContain('Transcripción exitosa')
    expect(wrapper.emitted('submit-draft')).toBeTruthy()
  })

  it('handles empty transcriptions without appending or emitting', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ text: '' })
    }))

    const store = useDebateStore()
    store.draftMessage = ''

    const wrapper = mount(ParticleOrb, {
      props: { isDebating: false, activeAgentColor: '#ffffff' }
    })

    const micButton = wrapper.find('#micButton')
    await micButton.trigger('click')
    await flushPromises()

    await micButton.trigger('click')
    await flushPromises()

    expect(store.draftMessage).toBe('')
    expect(wrapper.emitted('submit-draft')).toBeFalsy()
  })

  it('handles failed transcription response gracefully', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 500
    }))
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    const wrapper = mount(ParticleOrb, {
      props: { isDebating: false, activeAgentColor: '#ffffff' }
    })

    const micButton = wrapper.find('#micButton')
    await micButton.trigger('click')
    await flushPromises()
    await micButton.trigger('click')
    await flushPromises()

    expect(consoleErrorSpy).toHaveBeenCalledWith('Transcription failed')
  })

  it('handles transcription fetch network error gracefully', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Network offline')))
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    const wrapper = mount(ParticleOrb, {
      props: { isDebating: false, activeAgentColor: '#ffffff' }
    })

    const micButton = wrapper.find('#micButton')
    await micButton.trigger('click')
    await flushPromises()
    await micButton.trigger('click')
    await flushPromises()

    expect(consoleErrorSpy).toHaveBeenCalledWith('Transcription error:', expect.any(Error))
  })

  it('handles microphone access failure with alert', async () => {
    Object.defineProperty(navigator, 'mediaDevices', {
      value: {
        getUserMedia: vi.fn().mockRejectedValue(new Error('Permission denied'))
      },
      configurable: true,
      writable: true
    })

    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {})
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    const wrapper = mount(ParticleOrb, {
      props: { isDebating: false, activeAgentColor: '#ffffff' }
    })

    const micButton = wrapper.find('#micButton')
    await micButton.trigger('click')
    await flushPromises()

    expect(alertSpy).toHaveBeenCalledWith('No se pudo acceder al micrófono para dictado de voz.')
    expect(consoleErrorSpy).toHaveBeenCalledWith('Error accessing microphone:', expect.any(Error))
  })

  it('triggers toggleRecording when store.isWakeWordTriggered becomes true', async () => {
    const store = useDebateStore()
    const wrapper = mount(ParticleOrb, {
      props: { isDebating: false, activeAgentColor: '#ffffff' }
    })

    store.isWakeWordTriggered = true
    await wrapper.vm.$nextTick()
    await flushPromises()

    expect(store.isRecording).toBe(true)
    wrapper.unmount()
    store.isWakeWordTriggered = false
    store.isRecording = false
  })

  it('displays correct voice state text and indicator style when TTS is playing', async () => {
    const store = useDebateStore()
    store.globalAnalyser = {
      frequencyBinCount: 16,
      getByteTimeDomainData: vi.fn((arr: Uint8Array) => arr.fill(130))
    } as unknown as AnalyserNode
    store.isTtsPlaying = true

    const wrapper = mount(ParticleOrb, {
      props: { isDebating: false, activeAgentColor: '#a855f7' }
    })

    expect(wrapper.text()).toContain('ESTADO VOZ: ACTIVO')
    const dot = wrapper.find('#voiceIndicatorDot')
    expect(dot.attributes('style')).toContain('background-color: rgb(168, 85, 247)')
    wrapper.unmount()
    store.isTtsPlaying = false
    store.globalAnalyser = null
  })

  it('displays correct voice state text when auto listen is enabled', async () => {
    const store = useDebateStore()
    const wrapper = mount(ParticleOrb, {
      props: { isDebating: false, activeAgentColor: '#ffffff' }
    })

    store.isAutoListenEnabled = true
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('ESTADO VOZ: ESPERANDO WAKE WORD')
    wrapper.unmount()
    store.isAutoListenEnabled = false
  })

  it('performs silence detection with timers and auto-submits when quiet', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval'] })
    const store = useDebateStore()

    const wrapper = mount(ParticleOrb, {
      props: { isDebating: false, activeAgentColor: '#ffffff' }
    })

    const micButton = wrapper.find('#micButton')
    await micButton.trigger('click')
    await flushPromises()

    expect(store.isRecording).toBe(true)

    // Advance 1100ms for initial delay
    vi.advanceTimersByTime(1100)
    await flushPromises()

    // Advance 2100ms for silence timeout trigger
    vi.advanceTimersByTime(2100)
    await flushPromises()

    expect(store.isRecording).toBe(false)
    wrapper.unmount()
  })

  it('resets silence timer if audio frequency indicates user speaking', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval'] })
    const store = useDebateStore()

    let voiceSpeaking = false
    class SpeakingAudioContext extends MockAudioContext {
      createAnalyser() {
        return {
          minDecibels: -70,
          smoothingTimeConstant: 0.2,
          fftSize: 256,
          frequencyBinCount: 128,
          connect: vi.fn(),
          disconnect: vi.fn(),
          getByteFrequencyData: vi.fn((arr: Uint8Array) => {
            arr.fill(voiceSpeaking ? 50 : 0)
          }),
          getByteTimeDomainData: vi.fn()
        }
      }
    }
    vi.stubGlobal('AudioContext', SpeakingAudioContext)

    const wrapper = mount(ParticleOrb, {
      props: { isDebating: false, activeAgentColor: '#ffffff' }
    })

    const micButton = wrapper.find('#micButton')
    await micButton.trigger('click')
    await flushPromises()

    // Pass initial delay
    vi.advanceTimersByTime(1100)
    await flushPromises()

    // User speaks before silence timeout
    voiceSpeaking = true
    vi.advanceTimersByTime(300)
    await flushPromises()

    // Still recording because speaking reset the timer
    expect(store.isRecording).toBe(true)

    // Clean up
    await micButton.trigger('click')
    await flushPromises()
    wrapper.unmount()
  })

  it('handles window resize event and re-measures canvas dimensions', () => {
    const wrapper = mount(ParticleOrb, {
      props: { isDebating: false, activeAgentColor: '#ffffff' }
    })

    window.dispatchEvent(new Event('resize'))
    expect(wrapper.exists()).toBe(true)
  })

  it('renders correctly with multiple parallel active agents and custom ring colors', () => {
    const wrapper = mount(ParticleOrb, {
      props: {
        isDebating: true,
        activeAgentColor: '#00e5ff',
        activeAgents: [
          { role: 'investigador', name: 'Hermes', color: '#10b981' },
          { role: 'disruptor', name: 'Ícaro', color: '#f59e0b' }
        ]
      }
    })

    expect(wrapper.exists()).toBe(true)
    const ring1 = wrapper.find('#orbRing1')
    const ring2 = wrapper.find('#orbRing2')
    expect(ring1.attributes('style')).toMatch(/16,\s*185,\s*129|10b981/)
    expect(ring2.attributes('style')).toMatch(/245,\s*158,\s*11|f59e0b/)
  })

  it('renders correctly with all 8 council agents in parallel and generates multi-stop conic glow', () => {
    const eightAgents = [
      { role: 'supervisor', name: 'Atenea', color: '#f59e0b' },
      { role: 'nl_interpreter', name: 'Hermes', color: '#00e5ff' },
      { role: 'innovator_architect', name: 'Ícaro', color: '#22c55e' },
      { role: 'senior_architect', name: 'Hestia', color: '#00ff9d' },
      { role: 'the_judge', name: 'Sphinx', color: '#ef4444' },
      { role: 'devops_secops', name: 'Hefesto', color: '#ff8800' },
      { role: 'diagrammer', name: 'Aracne', color: '#b347ff' },
      { role: 'learning', name: 'Metis', color: '#1d4ed8' }
    ]

    const wrapper = mount(ParticleOrb, {
      props: {
        isDebating: true,
        activeAgentColor: '#f59e0b',
        activeAgents: eightAgents
      }
    })

    expect(wrapper.exists()).toBe(true)
    const glow1 = wrapper.find('#orbGlowCore1')
    const glow2 = wrapper.find('#orbGlowCore2')
    expect(glow1.attributes('style')).toContain('conic-gradient')
    // Conic gradient includes colors beyond the first 4 (converted to rgba by browser/jsdom)
    expect(glow1.attributes('style')).toMatch(/239,\s*68,\s*68|ef4444/)
    expect(glow1.attributes('style')).toMatch(/179,\s*71,\s*255|b347ff/)
    expect(glow1.attributes('style')).toMatch(/29,\s*78,\s*216|1d4ed8/)
    expect(glow2.attributes('style')).toContain('conic-gradient')
  })

  it('hides SoundBar on mobile viewports with hidden md:block, is always visible on desktop, and collapsible on tablet', async () => {
    // Desktop width (1440px)
    window.innerWidth = 1440
    window.innerHeight = 900
    const wrapper = mount(ParticleOrb, {
      props: {
        isDebating: false,
        activeAgentColor: '#f59e0b'
      }
    })

    const soundBarWrapper = wrapper.find('[data-test="soundbar-tablet-wrapper"]')
    expect(soundBarWrapper.exists()).toBe(true)
    expect(soundBarWrapper.classes()).toContain('hidden')
    expect(soundBarWrapper.classes()).toContain('md:block')
    expect(soundBarWrapper.classes()).toContain('relative')

    const soundBar = wrapper.findComponent({ name: 'SoundBar' })
    expect(soundBar.exists()).toBe(true)
    // On desktop, never collapsible, always visible
    expect(soundBar.props('collapsible')).toBe(false)
    expect(soundBar.find('[data-test="soundbar-body"]').attributes('style')).toBeFalsy()

    // Tablet width (820px)
    window.innerWidth = 820
    window.innerHeight = 900
    wrapper.vm.checkTabletCollapsible()
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.isTabletCollapsible).toBe(true)
    expect(soundBar.props('collapsible')).toBe(true)
    // Starts collapsed on tablet
    expect(soundBar.vm.isCollapsed).toBe(true)
    expect(soundBar.find('[data-test="soundbar-body"]').attributes('style')).toContain('display: none')

    // Click toggle button to deploy on tablet
    const toggleBtn = soundBar.find('[data-test="soundbar-collapse-toggle"]')
    await toggleBtn.trigger('click')
    await wrapper.vm.$nextTick()

    expect(soundBar.vm.isCollapsed).toBe(false)
    expect(soundBar.find('[data-test="soundbar-body"]').attributes('style')).toBeFalsy()

    // Click again to collapse on tablet
    await toggleBtn.trigger('click')
    await wrapper.vm.$nextTick()
    expect(soundBar.vm.isCollapsed).toBe(true)
    expect(soundBar.find('[data-test="soundbar-body"]').attributes('style')).toContain('display: none')

    // Clicking handle bar also deploys on tablet
    const handle = soundBar.find('[data-test="soundbar-collapse-handle"]')
    await handle.trigger('click')
    await wrapper.vm.$nextTick()
    expect(soundBar.vm.isCollapsed).toBe(false)
    expect(soundBar.find('[data-test="soundbar-body"]').attributes('style')).toBeFalsy()
  })

  it('initializes SoundBar already collapsed without any contraction effect when mounted on tablet', () => {
    window.innerWidth = 820
    window.innerHeight = 900
    const wrapper = mount(ParticleOrb, {
      props: {
        isDebating: false,
        activeAgentColor: '#f59e0b'
      }
    })

    expect(wrapper.vm.isTabletCollapsible).toBe(true)
    const soundBar = wrapper.findComponent({ name: 'SoundBar' })
    expect(soundBar.props('collapsible')).toBe(true)
    expect(soundBar.vm.isCollapsed).toBe(true)
    expect(soundBar.find('[data-test="soundbar-body"]').attributes('style')).toContain('display: none')
  })

  it('pauses canvas animation when isVisible becomes false or page is hidden, and omits SoundBar on mobile', async () => {
    window.innerWidth = 375
    window.innerHeight = 800
    const wrapper = mount(ParticleOrb, {
      props: {
        isDebating: false,
        activeAgentColor: '#00e5ff',
        isVisible: true
      }
    })

    // Only desktop/tablet mounts SoundBar inside ParticleOrb
    expect(wrapper.findComponent({ name: 'SoundBar' }).exists()).toBe(false)

    const initialCalls = requestAnimationFrameSpy.mock.calls.length
    await wrapper.setProps({ isVisible: false })
    expect(cancelAnimationFrameSpy).toHaveBeenCalled()

    await wrapper.setProps({ isVisible: true })
    expect(requestAnimationFrameSpy.mock.calls.length).toBeGreaterThan(initialCalls)

    // Document hidden pauses animation too
    const callsBeforeHide = cancelAnimationFrameSpy.mock.calls.length
    Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true })
    document.dispatchEvent(new Event('visibilitychange'))
    expect(cancelAnimationFrameSpy.mock.calls.length).toBeGreaterThan(callsBeforeHide)

    const rafCallsBeforeVisible = requestAnimationFrameSpy.mock.calls.length
    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true })
    document.dispatchEvent(new Event('visibilitychange'))
    expect(requestAnimationFrameSpy.mock.calls.length).toBeGreaterThan(rafCallsBeforeVisible)

    wrapper.unmount()
  })
})
