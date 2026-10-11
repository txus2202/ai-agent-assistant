import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useDebateStore } from '../debate'

interface MockWebSocketInstance {
  readyState: number
  send: ReturnType<typeof vi.fn>
  close: ReturnType<typeof vi.fn>
  addEventListener: ReturnType<typeof vi.fn>
  removeEventListener: ReturnType<typeof vi.fn>
  onopen: (() => void | Promise<void>) | null
  onclose: (() => void) | null
  onmessage: ((event: { data: string }) => void) | null
  onerror: ((err: unknown) => void) | null
}

describe('useDebateStore', () => {
  let originalWebSocket: typeof WebSocket
  let mockSend: ReturnType<typeof vi.fn>
  let activeSockets: MockWebSocketInstance[] = []

  beforeEach(() => {
    setActivePinia(createPinia())
    originalWebSocket = global.WebSocket
    mockSend = vi.fn()
    activeSockets = []
    class MockWebSocket {
      readyState = WebSocket.OPEN
      send = mockSend
      close = vi.fn()
      addEventListener = vi.fn()
      removeEventListener = vi.fn()
      onopen: (() => void) | null = null
      onclose: (() => void) | null = null
      onmessage: ((event: { data: string }) => void) | null = null
      onerror: ((err: unknown) => void) | null = null
      constructor() {
        activeSockets.push(this)
      }
    }
    global.WebSocket = MockWebSocket as unknown as typeof WebSocket

    class MockAudioContext {
      state = 'suspended'
      resume = vi.fn().mockResolvedValue(undefined)
      close = vi.fn().mockResolvedValue(undefined)
      destination = {}
      createAnalyser = vi.fn().mockReturnValue({
        fftSize: 256,
        connect: vi.fn()
      })
      createBuffer = vi.fn().mockReturnValue({})
      createBufferSource = vi.fn().mockImplementation(() => {
        const node = {
          buffer: null,
          connect: vi.fn(),
          start: vi.fn().mockImplementation(() => {
            if (node.onended) {
              node.onended()
            }
          }),
          stop: vi.fn(),
          disconnect: vi.fn(),
          onended: null as (() => void) | null
        }
        return node
      })
      decodeAudioData = vi.fn().mockImplementation(() => Promise.resolve({}))
      createMediaStreamSource = vi.fn().mockReturnValue({ connect: vi.fn(), disconnect: vi.fn() })
      createScriptProcessor = vi.fn().mockReturnValue({
        connect: vi.fn(),
        disconnect: vi.fn(),
        onaudioprocess: null
      })
      audioWorklet = {
        addModule: vi.fn().mockResolvedValue(undefined)
      }
    }
    global.AudioContext = MockAudioContext as unknown as typeof AudioContext
    ;(window as unknown as { AudioContext: typeof AudioContext }).AudioContext = MockAudioContext as unknown as typeof AudioContext

    class MockAudioWorkletNode {
      port = {
        onmessage: null as ((e: MessageEvent<Float32Array>) => void) | null,
        postMessage: vi.fn()
      }
      connect = vi.fn()
      disconnect = vi.fn()
    }
    vi.stubGlobal('AudioWorkletNode', MockAudioWorkletNode)
    URL.createObjectURL = vi.fn().mockReturnValue('blob:mock-worklet')
    URL.revokeObjectURL = vi.fn()
  })

  afterEach(() => {
    global.WebSocket = originalWebSocket
    vi.restoreAllMocks()
  })

  it('initializes with default state', () => {
    const store = useDebateStore()
    expect(store.isConnected).toBe(false)
    expect(store.isDebating).toBe(false)
    expect(store.isHitlRequired).toBe(false)
    expect(store.hitlCheckpoint).toBeNull()
    expect(store.messages).toEqual([])
    expect(store.agents).toHaveLength(0) // Now initialized empty
    expect(store.isAgentsLoaded).toBe(false)
  })

  it('handles loadAgents by setting agents from fetch', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([{ id: 'nl_interpreter', name: 'Nl Interpreter' }])
    })

    const store = useDebateStore()
    await store.loadAgents()

    expect(store.agents).toHaveLength(1)
    expect(store.agents[0]!.role).toBe('nl_interpreter')
    expect(store.agents[0]!.state).toBe('STANDBY')
    expect(store.isAgentsLoaded).toBe(true)
  })

  it('handles startDebate by setting states appropriately', () => {
    const store = useDebateStore()
    store.connect()
    
    // Set connected so it proceeds to send
    store.isConnected = true
    store.startDebate('test task', 'learning', '/tmp/file.pdf')
    
    expect(store.isDebating).toBe(true)
    expect(store.messages).toHaveLength(1)
    expect(store.messages[0]!.content).toBe('test task')
    expect(store.messages[0]!.role).toBe('user')
    // We can verify send was called on the mocked ws
    expect(mockSend).toHaveBeenCalledWith(JSON.stringify({ 
      type: 'start', 
      user_request: 'test task',
      target_agent: 'learning',
      attachments: ['/tmp/file.pdf']
    }))
  })

  it('handles startDebate with defaults', () => {
    const store = useDebateStore()
    store.connect()
    store.isConnected = true
    store.startDebate('test task')
    expect(mockSend).toHaveBeenCalledWith(JSON.stringify({ 
      type: 'start', 
      user_request: 'test task',
      target_agent: 'supervisor',
      attachments: []
    }))
  })

  it('handles uploadFile', async () => {
    const store = useDebateStore()
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ path: '/tmp/test.pdf' })
    })

    const file = new File([''], 'test.pdf')
    const path = await store.uploadFile(file)

    expect(path).toBe('/tmp/test.pdf')
    expect(global.fetch).toHaveBeenCalled()
  })

  it('handles HITL_REQUIRED event', () => {
    const store = useDebateStore()
    
    store.handleSupervisorEvent({
      type: 'hitl_required',
      role: null,
      content: 'Please approve the specs',
      metadata: { checkpoint: '1' }
    })
    
    expect(store.isHitlRequired).toBe(true)
    expect(store.hitlCheckpoint).toBe('1')
  })

  it('handles startAutoListen lifecycle, audio streaming, wake word detection, and cleanup', async () => {
    vi.useFakeTimers()
    const store = useDebateStore()

    const mockTrackStop = vi.fn()
    Object.defineProperty(global.navigator, 'mediaDevices', {
      value: {
        getUserMedia: vi.fn().mockResolvedValue({
          getTracks: () => [{ stop: mockTrackStop }]
        })
      },
      configurable: true,
      writable: true
    })

    class MockAudioWorkletNodeWithCapture {
      port = {
        onmessage: null as ((e: { data: Float32Array }) => void) | null,
        postMessage: vi.fn()
      }
      connect = vi.fn()
      disconnect = vi.fn()
      constructor() {
        createdProcessor = this
      }
    }
    let createdProcessor: MockAudioWorkletNodeWithCapture | null = null
    vi.stubGlobal('AudioWorkletNode', MockAudioWorkletNodeWithCapture)

    store.startAutoListen()
    expect(store.isAutoListenEnabled).toBe(true)

    // Early return if already enabled
    const initialSocketsCount = activeSockets.length
    store.startAutoListen()
    expect(activeSockets.length).toBe(initialSocketsCount)

    const wakeWordWs = activeSockets[activeSockets.length - 1]
    expect(wakeWordWs).toBeDefined()
    if (!wakeWordWs) throw new Error('wakeWordWs not initialized')

    // Trigger onopen
    await wakeWordWs.onopen?.()

    const processor = createdProcessor as unknown as MockAudioWorkletNodeWithCapture
    expect(processor).toBeDefined()
    expect(processor.port.onmessage).toBeDefined()

    // Simulate sending PCM audio data through AudioWorklet port
    const floatData = new Float32Array([0.5, -0.5, 0.0])
    processor.port.onmessage?.({ data: floatData })
    expect(mockSend).toHaveBeenCalledWith(expect.any(ArrayBuffer))

    // If store is recording, it should skip sending
    mockSend.mockClear()
    store.isRecording = true
    processor.port.onmessage?.({ data: floatData })
    expect(mockSend).not.toHaveBeenCalled()
    store.isRecording = false

    // Simulate wake word detected event from server
    store.isTtsPlaying = true
    wakeWordWs.onmessage?.({
      data: JSON.stringify({ type: 'WAKE_WORD_DETECTED' })
    })

    expect(store.isTtsPlaying).toBe(false)
    expect(store.isWakeWordTriggered).toBe(true)

    // Fast forward 1000ms timer to reset wake word trigger
    vi.advanceTimersByTime(1100)
    expect(store.isWakeWordTriggered).toBe(false)

    // Trigger onclose callback
    wakeWordWs.onclose?.()
    expect(store.isAutoListenEnabled).toBe(false)
    expect(mockTrackStop).toHaveBeenCalled()

    vi.useRealTimers()
  })

  it('handles startAutoListen getUserMedia error gracefully', async () => {
    const store = useDebateStore()

    Object.defineProperty(global.navigator, 'mediaDevices', {
      value: {
        getUserMedia: vi.fn().mockRejectedValue(new Error('Mic not found'))
      },
      configurable: true,
      writable: true
    })

    store.startAutoListen()
    const wakeWordWs = activeSockets[activeSockets.length - 1]
    if (!wakeWordWs) throw new Error('wakeWordWs not initialized')

    await wakeWordWs.onopen?.()
    expect(store.isAutoListenEnabled).toBe(false)
  })

  it('updates agent states on agent_started and agent_completed events', () => {
    const store = useDebateStore()
    store.agents = [
      { role: 'diagrammer', name: 'Diagrammer', state: 'STANDBY' }
    ]

    store.handleSupervisorEvent({
      type: 'agent_started',
      role: 'diagrammer',
      content: 'Generating diagrams'
    })
    expect(store.agents[0]!.state).toBe('ACTIVE')

    store.handleSupervisorEvent({
      type: 'agent_completed',
      role: 'diagrammer',
      content: 'Diagram created'
    })
    expect(store.agents[0]!.state).toBe('COMPLETED')
  })

  it('handles done, error, and message supervisor events', () => {
    const store = useDebateStore()
    store.isDebating = true

    // message event
    store.handleSupervisorEvent({
      type: 'message',
      role: 'senior_architect',
      content: 'Design review looks solid.'
    })
    expect(store.messages).toHaveLength(1)
    expect(store.messages[0]!.content).toBe('[senior_architect] Design review looks solid.')

    // error event
    store.handleSupervisorEvent({
      type: 'error',
      role: null,
      content: 'Connection lost with agent'
    })
    expect(store.isDebating).toBe(false)
    expect(store.messages).toHaveLength(2)
    expect(store.messages[1]!.content).toContain('Error: Connection lost with agent')

    // done event
    store.handleSupervisorEvent({
      type: 'done',
      role: 'the_judge',
      content: 'Consensus finalized.'
    })
    expect(store.isDebating).toBe(false)
    expect(store.messages).toHaveLength(3)
    expect(store.messages[2]!.content).toBe('[the_judge] Consensus finalized.')
  })

  it('handles submitHitlDecision by sending websocket payload and resetting checkpoint', () => {
    const store = useDebateStore()
    store.connect()
    store.isConnected = true
    store.isHitlRequired = true
    store.hitlCheckpoint = 'CP-A'

    store.submitHitlDecision('refine', 'Add authentication layers')

    expect(store.isHitlRequired).toBe(false)
    expect(store.hitlCheckpoint).toBeNull()
    expect(mockSend).toHaveBeenCalledWith(JSON.stringify({
      type: 'hitl_response',
      decision: 'refine',
      feedback: 'Add authentication layers'
    }))
  })

  it('handles loadDebate by restoring sessions, agents to standby, and replaying events', () => {
    const store = useDebateStore()
    store.agents = [
      { role: 'nl_interpreter', name: 'NL Interpreter', state: 'ACTIVE' }
    ]

    const historicalDebate = {
      id: 'session-42',
      status: 'completed' as const,
      created_at: '2026-10-11T10:00:00Z',
      user_request: 'Create a payment gateway architecture',
      events: [
        { type: 'agent_started', role: 'nl_interpreter', content: 'Parsing' },
        { type: 'agent_completed', role: 'nl_interpreter', content: 'Finished' },
        { type: 'done', role: 'the_judge', content: 'Debate concluded' }
      ]
    }

    store.loadDebate(historicalDebate)

    expect(store.agents[0]!.state).toBe('COMPLETED')
    expect(store.isDebating).toBe(false)
    expect(store.messages).toHaveLength(2) // 1 user request + 1 done message
    expect(store.messages[0]!.content).toBe('Create a payment gateway architecture')
    expect(store.rawEvents).toHaveLength(3)
  })

  it('handles loadAgents fallback when backend API fails', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error'))

    const store = useDebateStore()
    await store.loadAgents()

    expect(store.isAgentsLoaded).toBe(true)
    expect(store.agents.length).toBeGreaterThanOrEqual(6)
    expect(store.agents.some(a => a.role === 'the_judge')).toBe(true)
  })

  it('handles startDebate when disconnected by showing error message and calling connect', () => {
    const store = useDebateStore()
    store.isConnected = false

    store.startDebate('Offline request')

    expect(store.messages).toHaveLength(1)
    expect(store.messages[0]!.content).toContain('Cannot start debate, disconnected')
  })

  it('stops TTS and resets active role', () => {
    const store = useDebateStore()
    store.isTtsPlaying = true
    store.activeTtsRole = 'the_judge'

    store.stopTts()

    expect(store.isTtsPlaying).toBe(false)
    expect(store.activeTtsRole).toBeNull()
  })

  it('handles websocket open, message, error, and close lifecycle events', () => {
    const store = useDebateStore()
    store.connect()

    const wsInstance = activeSockets[0]
    expect(wsInstance).toBeDefined()
    if (!wsInstance) throw new Error('wsInstance not initialized')

    // 1. onopen
    wsInstance.onopen?.()
    expect(store.isConnected).toBe(true)

    // 2. onmessage with valid data
    wsInstance.onmessage?.({
      data: JSON.stringify({ type: 'message', role: 'supervisor', content: 'Debate stream initialized.' })
    })
    expect(store.rawEvents).toHaveLength(1)
    expect(store.messages).toHaveLength(1)
    expect(store.messages[0]!.content).toBe('[supervisor] Debate stream initialized.')

    // 3. onmessage with invalid JSON does not throw
    wsInstance.onmessage?.({ data: 'invalid json payload' })
    expect(store.rawEvents).toHaveLength(1)

    // 4. onerror
    wsInstance.onerror?.(new Error('Network drop'))

    // 5. onclose
    wsInstance.onclose?.()
    expect(store.isConnected).toBe(false)
  })

  it('avoids re-creating websocket when already connected or connecting', () => {
    const store = useDebateStore()
    store.connect()
    expect(activeSockets).toHaveLength(1)

    // Call connect again while OPEN
    store.connect()
    expect(activeSockets).toHaveLength(1)
  })

  it('unlocks audio context and primes with silent buffer source', () => {
    const store = useDebateStore()
    store.unlockAudioContext()

    // Dispatches user gesture to trigger unlockAudioContext listeners
    window.dispatchEvent(new Event('pointerdown'))
    window.dispatchEvent(new Event('keydown'))
    window.dispatchEvent(new Event('touchstart'))

    expect(store.globalAnalyser).toBeDefined()
  })

  it('handles playTtsAudioChunk gracefully based on isTtsPlaying state', async () => {
    const store = useDebateStore()

    // When TTS is not playing, should return early
    store.isTtsPlaying = false
    await store.playTtsAudioChunk(new ArrayBuffer(16))

    // When TTS is playing, should decode and play
    store.isTtsPlaying = true
    const playPromise = store.playTtsAudioChunk(new ArrayBuffer(16))
    expect(playPromise).toBeInstanceOf(Promise)
    await playPromise
  })
})
