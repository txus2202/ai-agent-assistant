import { describe, it, expect, vi, beforeEach, afterEach, type MockInstance } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import SoundBar from '../SoundBar.vue'
import { useDebateStore } from '../../stores/debate'

describe('SoundBar.vue', () => {
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
          arr.fill(0)
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
      fillRect: vi.fn(),
      lineWidth: 1,
      strokeStyle: '',
      fillStyle: ''
    })) as unknown as HTMLCanvasElement['getContext']

    window.requestAnimationFrame = vi.fn().mockImplementation(() => 1)
    window.cancelAnimationFrame = vi.fn()
    requestAnimationFrameSpy = vi.spyOn(window, 'requestAnimationFrame')
    cancelAnimationFrameSpy = vi.spyOn(window, 'cancelAnimationFrame')

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
      json: () => Promise.resolve({ text: 'Hola mundo' })
    }))
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  it('mounts properly and renders row 1 with mic button and waveform canvas sharing the same height', () => {
    const wrapper = mount(SoundBar, {
      props: {
        activeAgentColor: '#f59e0b'
      }
    })

    const micBtn = wrapper.find('#micButton')
    expect(micBtn.exists()).toBe(true)
    expect(micBtn.classes()).toContain('h-[44px]')

    const waveformCanvas = wrapper.find('#waveformCanvas')
    expect(waveformCanvas.exists()).toBe(true)
    expect(waveformCanvas.classes()).toContain('h-[44px]')
    expect(requestAnimationFrameSpy).toHaveBeenCalled()
  })

  it('renders centered voice state caption directly in row 2 below controls', () => {
    const wrapper = mount(SoundBar)

    const indicatorDot = wrapper.find('#voiceIndicatorDot')
    expect(indicatorDot.exists()).toBe(true)

    const caption = wrapper.find('#voiceStateCaption')
    expect(caption.exists()).toBe(true)
    expect(caption.text()).toBe('ESTADO VOZ: EN REPOSO')
  })

  it('renders 3D view switch button only when showViewSwitch is true and emits open-voice on click', async () => {
    const wrapper = mount(SoundBar, {
      props: {
        showViewSwitch: false
      }
    })
    expect(wrapper.find('[data-test="soundbar-view-switch"]').exists()).toBe(false)

    await wrapper.setProps({ showViewSwitch: true })
    const switchBtn = wrapper.find('[data-test="soundbar-view-switch"]')
    expect(switchBtn.exists()).toBe(true)

    await switchBtn.trigger('click')
    expect(wrapper.emitted('open-voice')).toHaveLength(1)
  })

  it('toggles recording on click, processes audio and emits submit-draft', async () => {
    const store = useDebateStore()
    const stopTtsSpy = vi.spyOn(store, 'stopTts')
    const unlockSpy = vi.spyOn(store, 'unlockAudioContext')

    const wrapper = mount(SoundBar, {
      props: {
        activeAgentColor: '#f59e0b'
      }
    })

    const micBtn = wrapper.find('#micButton')
    await micBtn.trigger('click')
    await flushPromises()

    expect(stopTtsSpy).toHaveBeenCalled()
    expect(unlockSpy).toHaveBeenCalled()
    expect(store.isRecording).toBe(true)
    expect(wrapper.text()).toContain('ESCUCHANDO...')
    expect(wrapper.text()).toContain('ESTADO VOZ: ESCUCHANDO ORDEN')

    const recorder = createdRecorders[0]
    expect(recorder).toBeDefined()
    expect(recorder!.state).toBe('recording')

    // Stop recording
    await micBtn.trigger('click')
    await flushPromises()

    expect(store.isRecording).toBe(false)
    expect(wrapper.emitted('submit-draft')).toHaveLength(1)
    expect(store.draftMessage).toContain('Hola mundo')
  })

  it('cancels animation frame and cleans up on unmount', () => {
    const wrapper = mount(SoundBar)
    wrapper.unmount()
    expect(cancelAnimationFrameSpy).toHaveBeenCalled()
  })

  it('handles collapsible mode with arrow toggle button and touch swipe', async () => {
    const wrapper = mount(SoundBar, {
      props: {
        collapsible: true,
        initialCollapsed: false
      }
    })

    // Handle bar is rendered when collapsible is true
    const handle = wrapper.find('[data-test="soundbar-collapse-handle"]')
    expect(handle.exists()).toBe(true)

    expect(wrapper.find('[data-test="soundbar-body"]').attributes('style')).toBeFalsy()

    // Click toggle button to collapse
    const toggleBtn = wrapper.find('[data-test="soundbar-collapse-toggle"]')
    await toggleBtn.trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.isCollapsed).toBe(true)
    expect(wrapper.find('[data-test="soundbar-body"]').attributes('style')).toContain('display: none')
    // When collapsed, handle bar displays voice status and MIC tag
    expect(handle.text()).toContain('ESTADO VOZ: EN REPOSO')
    expect(handle.text()).toContain('MIC')

    // Swipe up on container to expand
    const container = wrapper.find('[data-test="sound-bar"]')
    await container.trigger('touchstart', {
      touches: [{ clientX: 100, clientY: 200 }],
      changedTouches: [{ clientX: 100, clientY: 200 }]
    })
    await container.trigger('touchend', {
      changedTouches: [{ clientX: 100, clientY: 100 }]
    })
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.isCollapsed).toBe(false)
    expect(wrapper.find('[data-test="soundbar-body"]').attributes('style')).toBeFalsy()
    // When deployed, handle bar doesn't have the duplicate text or stray dot
    expect(handle.text()).not.toContain('ESTADO VOZ')
    expect(handle.text()).not.toContain('MIC')

    // Swipe down to collapse
    await container.trigger('touchstart', {
      touches: [{ clientX: 100, clientY: 100 }],
      changedTouches: [{ clientX: 100, clientY: 100 }]
    })
    await container.trigger('touchend', {
      changedTouches: [{ clientX: 100, clientY: 200 }]
    })
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.isCollapsed).toBe(true)
    expect(wrapper.find('[data-test="soundbar-body"]').attributes('style')).toContain('display: none')

    // Clicking handle bar when collapsed expands it
    await handle.trigger('click')
    await wrapper.vm.$nextTick()
    expect(wrapper.vm.isCollapsed).toBe(false)
    expect(wrapper.find('[data-test="soundbar-body"]').attributes('style')).toBeFalsy()
  })

  it('supports touch and pointer swipe gestures directly on the soundbar-collapse-handle button', async () => {
    const wrapper = mount(SoundBar, {
      props: {
        collapsible: true,
        initialCollapsed: true
      }
    })

    expect(wrapper.vm.isCollapsed).toBe(true)

    const handle = wrapper.find('[data-test="soundbar-collapse-handle"]')
    expect(handle.exists()).toBe(true)

    // Swipe UP starting directly on the <button data-test="soundbar-collapse-handle">
    handle.element.dispatchEvent(
      new TouchEvent('touchstart', {
        bubbles: true,
        touches: [{ clientX: 100, clientY: 200 } as unknown as Touch],
      }),
    )
    handle.element.dispatchEvent(
      new TouchEvent('touchend', {
        bubbles: true,
        changedTouches: [{ clientX: 100, clientY: 110 } as unknown as Touch],
      }),
    )
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.isCollapsed).toBe(false)

    // Swipe DOWN starting directly on the <button data-test="soundbar-collapse-handle">
    handle.element.dispatchEvent(
      new TouchEvent('touchstart', {
        bubbles: true,
        touches: [{ clientX: 100, clientY: 110 } as unknown as Touch],
      }),
    )
    handle.element.dispatchEvent(
      new TouchEvent('touchend', {
        bubbles: true,
        changedTouches: [{ clientX: 100, clientY: 200 } as unknown as Touch],
      }),
    )
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.isCollapsed).toBe(true)
  })

  it('expands automatically and starts recording when store.isWakeWordTriggered becomes true while collapsed with listenWakeWord=true', async () => {
    const store = useDebateStore()
    const wrapper = mount(SoundBar, {
      props: {
        collapsible: true,
        initialCollapsed: true,
        listenWakeWord: true
      }
    })

    expect(wrapper.vm.isCollapsed).toBe(true)

    // Trigger wake word in store
    store.isWakeWordTriggered = true
    await flushPromises()
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.isCollapsed).toBe(false)
    expect(wrapper.vm.isRecording).toBe(true)
    expect(store.isRecording).toBe(true)
  })

  it('expands automatically when toggleRecording is invoked on a collapsed bar', async () => {
    const wrapper = mount(SoundBar, {
      props: {
        collapsible: true,
        initialCollapsed: true
      }
    })

    expect(wrapper.vm.isCollapsed).toBe(true)
    await wrapper.vm.toggleRecording()
    await flushPromises()
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.isCollapsed).toBe(false)
    expect(wrapper.vm.isRecording).toBe(true)
  })

  it('does NOT collapse automatically when submitting draft (only user can collapse)', async () => {
    const wrapper = mount(SoundBar, {
      props: {
        collapsible: true,
        initialCollapsed: false
      }
    })

    expect(wrapper.vm.isCollapsed).toBe(false)
    await wrapper.vm.toggleRecording()
    await flushPromises()

    // Stop recording and trigger transcription/submit
    await wrapper.vm.toggleRecording()
    await flushPromises()
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('submit-draft')).toHaveLength(1)
    // Must remain expanded
    expect(wrapper.vm.isCollapsed).toBe(false)
  })
})

