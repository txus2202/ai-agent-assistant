import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useDebateStore, normalizeAgentRole, cleanAgentMessageContent } from '../debate'

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
    expect(store.currentSessionId).toBeTruthy()
    expect(store.messages).toHaveLength(1)
    expect(store.messages[0]!.content).toBe('test task')
    expect(store.messages[0]!.role).toBe('user')
    // We can verify send was called on the mocked ws with session_id
    expect(JSON.parse(mockSend.mock.calls[0]![0])).toEqual({ 
      type: 'start', 
      session_id: store.currentSessionId,
      user_request: 'test task',
      target_agent: 'learning',
      attachments: ['/tmp/file.pdf'],
      history: []
    })
  })

  it('handles startDebate with defaults', () => {
    const store = useDebateStore()
    store.connect()
    store.isConnected = true
    store.startDebate('test task')
    expect(JSON.parse(mockSend.mock.calls[0]![0])).toEqual({ 
      type: 'start', 
      session_id: store.currentSessionId,
      user_request: 'test task',
      target_agent: 'supervisor',
      attachments: [],
      history: []
    })
  })

  it('handles startDebate and sends previous chat history in payload', () => {
    const store = useDebateStore()
    store.connect()
    store.isConnected = true
    store.messages.push(
      { id: '1', role: 'user', content: '¿Qué opinas de Docker?' },
      { id: '2', role: 'assistant', agentName: 'Hefesto', agentRole: 'devops_secops', content: 'Es excelente para aislar servicios.' }
    )

    store.startDebate('Sphinx, audita esta idea', 'the_judge')

    expect(JSON.parse(mockSend.mock.calls[0]![0])).toEqual({
      type: 'start',
      session_id: store.currentSessionId,
      user_request: 'Sphinx, audita esta idea',
      target_agent: 'the_judge',
      attachments: [],
      history: [
        { role: 'user', content: '¿Qué opinas de Docker?', agent: undefined },
        { role: 'assistant', content: 'Es excelente para aislar servicios.', agent: 'Hefesto' }
      ]
    })
  })

  it('handles multi-turn conversation preserving currentSessionId across multiple startDebate calls and accumulating tokens', () => {
    const store = useDebateStore()
    store.connect()
    store.isConnected = true

    // Turn 1
    store.startDebate('Hola Sphinx', 'the_judge')
    const firstSessionId = store.currentSessionId
    expect(firstSessionId).toBeTruthy()

    // Simulate Agent completion
    store.agents = [{ role: 'the_judge', name: 'Sphinx', state: 'ACTIVE' }]
    store.handleSupervisorEvent({
      type: 'agent_completed',
      role: 'the_judge',
      content: 'Respuesta 1',
      metadata: { tokens: '50' }
    })
    expect(store.sessionTotalTokens).toBe(50)

    // Turn 2
    store.startDebate('Hefesto, prepara el pipeline', 'devops_secops')
    expect(store.currentSessionId).toBe(firstSessionId)
    // Tokens must NOT reset to 0 in a continuous session
    expect(store.sessionTotalTokens).toBe(50)

    store.agents = [{ role: 'devops_secops', name: 'Hefesto', state: 'ACTIVE' }]
    store.handleSupervisorEvent({
      type: 'agent_completed',
      role: 'devops_secops',
      content: 'Respuesta 2',
      metadata: { tokens: '60' }
    })
    expect(store.sessionTotalTokens).toBe(110)
  })

  it('handles clearSession resetting messages, tokens, and currentSessionId', () => {
    const store = useDebateStore()
    store.currentSessionId = 'some-session'
    store.sessionTotalTokens = 150
    store.sessionCachedTokens = 75
    store.messages.push({ role: 'user', content: 'hello' })
    store.rawEvents.push({ type: 'done', content: 'ok' })

    store.clearSession()

    expect(store.currentSessionId).toBeNull()
    expect(store.sessionTotalTokens).toBe(0)
    expect(store.sessionCachedTokens).toBe(0)
    expect(store.messages).toHaveLength(0)
    expect(store.rawEvents).toHaveLength(0)
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
    }
    let createdProcessor: MockAudioWorkletNodeWithCapture | null = null
    const MockNodeProxy = new Proxy(MockAudioWorkletNodeWithCapture, {
      construct(target, args) {
        const instance = Reflect.construct(target, args) as MockAudioWorkletNodeWithCapture
        createdProcessor = instance
        return instance
      }
    })
    vi.stubGlobal('AudioWorkletNode', MockNodeProxy)

    store.startAutoListen()
    expect(store.isAutoListenEnabled).toBe(true)

    // Early return if already enabled
    const initialSocketsCount = activeSockets.length
    store.startAutoListen()
    expect(activeSockets).toHaveLength(initialSocketsCount)

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

    // Simulate wake word detected event from server with specific agent
    store.isTtsPlaying = true
    expect(store.selectedAgent).toBe('supervisor')
    wakeWordWs.onmessage?.({
      data: JSON.stringify({
        type: 'WAKE_WORD_DETECTED',
        agent_role: 'the_judge',
        display_name: 'Sphinx'
      })
    })

    expect(store.isTtsPlaying).toBe(false)
    expect(store.isWakeWordTriggered).toBe(true)
    expect(store.selectedAgent).toBe('the_judge')

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
    vi.spyOn(console, 'error').mockImplementation(() => {})
    vi.spyOn(console, 'log').mockImplementation(() => {})
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
    expect(store.agents[0]!.startedAt).toBeDefined()

    store.handleSupervisorEvent({
      type: 'agent_completed',
      role: 'diagrammer',
      content: 'Diagram created with flow',
      metadata: { latency_seconds: '1.25', tokens: '42' }
    })
    expect(store.agents[0]!.state).toBe('COMPLETED')
    expect(store.agents[0]!.latency).toBe(1.25)
    expect(store.agents[0]!.tokens).toBe(42)
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
    expect(store.messages[0]!.content).toBe('Design review looks solid.')

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
    expect(store.messages[2]!.content).toBe('Consensus finalized.')
  })

  it('populates agentRole, agentName, and colorHex on hitl_required and done events', () => {
    const store = useDebateStore()
    store.agents = [
      { role: 'nl_interpreter', name: 'Natural Language Interpreter', color_hex: '#00e5ff', state: 'STANDBY' },
      { role: 'supervisor', name: 'Supervisor', color_hex: '#f59e0b', state: 'STANDBY' }
    ]

    store.handleSupervisorEvent({
      type: 'hitl_required',
      role: 'nl_interpreter',
      content: 'Please confirm user request interpretation',
      metadata: { checkpoint: '1_interpreter' }
    })

    expect(store.isHitlRequired).toBe(true)
    expect(store.messages[0]!.agentRole).toBe('nl_interpreter')
    expect(store.messages[0]!.agentName).toBe('Natural Language Interpreter')
    expect(store.messages[0]!.colorHex).toBe('#00e5ff')
    expect(store.messages[0]!.content).not.toContain('[nl_interpreter]')
    expect(store.messages[0]!.content).toBe('Please confirm user request interpretation')

    store.handleSupervisorEvent({
      type: 'done',
      role: 'supervisor',
      content: 'Debate consolidated recommendation'
    })

    expect(store.messages[1]!.agentRole).toBe('supervisor')
    expect(store.messages[1]!.agentName).toBe('Supervisor')
    expect(store.messages[1]!.colorHex).toBe('#f59e0b')
  })

  it('handles submitHitlDecision by sending websocket payload, resetting checkpoint, and adding user message for refinement', () => {
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
    expect(store.messages).toHaveLength(1)
    expect(store.messages[0]).toMatchObject({
      role: 'user',
      content: 'Add authentication layers'
    })
  })

  it('does not add user message when approving without feedback', () => {
    const store = useDebateStore()
    store.connect()
    store.isConnected = true
    store.isHitlRequired = true
    store.hitlCheckpoint = 'CP-A'

    store.submitHitlDecision('approve')
    expect(store.messages).toHaveLength(0)
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

    expect(store.currentSessionId).toBe('session-42')
    expect(store.agents[0]!.state).toBe('COMPLETED')
    expect(store.isDebating).toBe(false)
    expect(store.messages).toHaveLength(2) // 1 user request + 1 done message
    expect(store.messages[0]!.content).toBe('Create a payment gateway architecture')
    expect(store.rawEvents).toHaveLength(3)
  })

  it('handles loadDebate with multi-turn user_message events restoring full dialogue in chronological order', () => {
    const store = useDebateStore()
    const historicalMultiTurn = {
      id: 'session-multi-turn-99',
      status: 'completed' as const,
      created_at: '2026-10-11T10:00:00Z',
      user_request: 'Turno inicial',
      events: [
        { type: 'user_message', role: 'user', content: 'Hola Sphinx' },
        { type: 'done', role: 'the_judge', content: 'Respuesta Sphinx' },
        { type: 'user_message', role: 'user', content: 'Hefesto despliega' },
        { type: 'done', role: 'devops_secops', content: 'Respuesta Hefesto' }
      ]
    }

    store.loadDebate(historicalMultiTurn)

    expect(store.currentSessionId).toBe('session-multi-turn-99')
    expect(store.messages).toHaveLength(4)
    expect(store.messages[0]!.role).toBe('user')
    expect(store.messages[0]!.content).toBe('Hola Sphinx')
    expect(store.messages[1]!.content).toBe('Respuesta Sphinx')
    expect(store.messages[2]!.role).toBe('user')
    expect(store.messages[2]!.content).toBe('Hefesto despliega')
    expect(store.messages[3]!.content).toBe('Respuesta Hefesto')
  })

  it('handles loadAgents error when backend API fails by clearing agents and resetting isAgentsLoaded', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error'))

    const store = useDebateStore()
    await store.loadAgents()

    expect(store.isAgentsLoaded).toBe(false)
    expect(store.agents).toEqual([])
  })

  it('handles loadAgents successfully mapping description and color_hex from API', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([
        { id: 'nl_interpreter', name: 'NL Interpreter', description: 'Formaliza intención', color_hex: '#00e5ff' }
      ])
    })

    const store = useDebateStore()
    await store.loadAgents()

    expect(store.isAgentsLoaded).toBe(true)
    expect(store.agents).toHaveLength(1)
    expect(store.agents[0]!.description).toBe('Formaliza intención')
    expect(store.agents[0]!.color_hex).toBe('#00e5ff')
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
    vi.spyOn(console, 'error').mockImplementation(() => {})
    vi.spyOn(console, 'log').mockImplementation(() => {})
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
    expect(store.messages[0]!.content).toBe('Debate stream initialized.')

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

  it('normalizes agent roles correctly (both standalone and on store)', () => {
    const store = useDebateStore()
    expect(normalizeAgentRole('')).toBe('')
    expect(normalizeAgentRole(null)).toBe('')
    expect(normalizeAgentRole(undefined)).toBe('')
    expect(normalizeAgentRole('INNOVATOR')).toBe('innovator_architect')
    expect(normalizeAgentRole('innovator')).toBe('innovator_architect')
    expect(normalizeAgentRole('nl-interpreter')).toBe('nl_interpreter')
    expect(normalizeAgentRole('supervisor')).toBe('supervisor')

    expect(store.normalizeAgentRole('innovator')).toBe('innovator_architect')
  })

  it('sends HITL response with target_agents via submitHitlDecision', () => {
    const store = useDebateStore()
    store.connect()

    const ws = activeSockets[0]
    expect(ws).toBeDefined()

    store.isHitlRequired = true
    store.hitlCheckpoint = 'after_nl_interpreter'

    store.submitHitlDecision('approve', 'Proceed with Redis', ['diagrammer', 'devops_secops'])

    expect(store.isHitlRequired).toBe(false)
    expect(store.hitlCheckpoint).toBeNull()

    expect(mockSend).toHaveBeenCalledWith(JSON.stringify({
      type: 'hitl_response',
      decision: 'approve',
      feedback: 'Proceed with Redis',
      target_agents: ['diagrammer', 'devops_secops']
    }))
  })

  it('reacts to HITL_VOICE_COMMAND messages from wake-word websocket', async () => {
    // Mock navigator.mediaDevices.getUserMedia
    const mockGetUserMedia = vi.fn().mockResolvedValue({
      getTracks: () => [{ stop: vi.fn() }]
    })
    Object.defineProperty(navigator, 'mediaDevices', {
      value: { getUserMedia: mockGetUserMedia },
      writable: true,
      configurable: true
    })

    const store = useDebateStore()
    store.connect()
    store.startAutoListen()

    // Wake word socket is the latest socket created
    const wwSocket = activeSockets[activeSockets.length - 1]
    expect(wwSocket).toBeDefined()

    // 1. Voice command "approve" when HITL is required
    store.isHitlRequired = true
    wwSocket!.onmessage?.({
      data: JSON.stringify({
        type: 'HITL_VOICE_COMMAND',
        command: 'approve'
      })
    })

    expect(store.isHitlRequired).toBe(false)
    expect(mockSend).toHaveBeenCalledWith(JSON.stringify({
      type: 'hitl_response',
      decision: 'approve',
      feedback: ''
    }))

    // 2. Voice command "finish" when HITL is required
    store.isHitlRequired = true
    wwSocket!.onmessage?.({
      data: JSON.stringify({
        type: 'HITL_VOICE_COMMAND',
        command: 'finish'
      })
    })

    expect(store.isHitlRequired).toBe(false)
    expect(mockSend).toHaveBeenCalledWith(JSON.stringify({
      type: 'hitl_response',
      decision: 'finish',
      feedback: ''
    }))

    // 3. Voice command "divert" when HITL is required
    store.isHitlRequired = true
    wwSocket!.onmessage?.({
      data: JSON.stringify({
        type: 'HITL_VOICE_COMMAND',
        command: 'divert'
      })
    })

    expect(store.isHitlRequired).toBe(false)
    expect(mockSend).toHaveBeenCalledWith(JSON.stringify({
      type: 'hitl_response',
      decision: 'divert',
      feedback: ''
    }))

    // 4. Voice command "refine" when HITL is required -> triggers wake word recording mode
    vi.useFakeTimers()
    store.isHitlRequired = true
    wwSocket!.onmessage?.({
      data: JSON.stringify({
        type: 'HITL_VOICE_COMMAND',
        command: 'refine'
      })
    })

    expect(store.isWakeWordTriggered).toBe(true)

    // Verify it automatically resets to false after delay to unblock future wake words
    vi.advanceTimersByTime(1000)
    expect(store.isWakeWordTriggered).toBe(false)
    vi.useRealTimers()

    // 3. submitHitlDecision sends RESET message to wakeWordWs and resets flags
    store.isWakeWordTriggered = true
    store.isRecording = true
    store.submitHitlDecision('approve')
    expect(store.isWakeWordTriggered).toBe(false)
    expect(store.isRecording).toBe(false)
    expect(mockSend).toHaveBeenCalledWith(JSON.stringify({ type: 'RESET' }))

    store.stopAutoListen()
  })

  it('toggles agent selection in HITL when saying agent names during HITL, and acts as regular wake word when HITL is inactive', () => {
    const mockGetUserMedia = vi.fn().mockResolvedValue({
      getTracks: () => [{ stop: vi.fn() }]
    })
    Object.defineProperty(navigator, 'mediaDevices', {
      value: { getUserMedia: mockGetUserMedia },
      writable: true,
      configurable: true
    })

    const store = useDebateStore()
    store.agents = [
      { role: 'senior_architect', name: 'Hestia', state: 'STANDBY' },
      { role: 'innovator_architect', name: 'Ícaro', state: 'STANDBY' },
      { role: 'supervisor', name: 'Atenea', state: 'STANDBY' }
    ]
    store.connect()
    store.startAutoListen()

    const wwSocket = activeSockets[activeSockets.length - 1]
    expect(wwSocket).toBeDefined()

    // 1. With HITL active
    store.isHitlRequired = true
    store.selectedAgent = 'supervisor'

    // Say "Hestia" -> selects Hestia
    wwSocket!.onmessage?.({
      data: JSON.stringify({
        type: 'WAKE_WORD_DETECTED',
        agent_role: 'senior_architect',
        display_name: 'Hestia'
      })
    })

    expect(store.hitlTargetAgents).toEqual(['senior_architect'])
    expect(store.selectedAgent).toBe('supervisor')
    expect(store.isWakeWordTriggered).toBe(false)

    // Say "Ícaro" -> selects Ícaro as well
    wwSocket!.onmessage?.({
      data: JSON.stringify({
        type: 'WAKE_WORD_DETECTED',
        agent_role: 'innovator_architect',
        display_name: 'Ícaro'
      })
    })

    expect(store.hitlTargetAgents).toEqual(['senior_architect', 'innovator_architect'])
    expect(store.selectedAgent).toBe('supervisor')
    expect(store.isWakeWordTriggered).toBe(false)

    // Say "Hestia" again -> deselects Hestia, leaving only Ícaro
    wwSocket!.onmessage?.({
      data: JSON.stringify({
        type: 'WAKE_WORD_DETECTED',
        agent_role: 'senior_architect',
        display_name: 'Hestia'
      })
    })

    expect(store.hitlTargetAgents).toEqual(['innovator_architect'])
    expect(store.selectedAgent).toBe('supervisor')
    expect(store.isWakeWordTriggered).toBe(false)

    // 2. Without HITL (regular mode)
    store.isHitlRequired = false

    // Say "Hestia" -> triggers regular wake word for Hestia
    wwSocket!.onmessage?.({
      data: JSON.stringify({
        type: 'WAKE_WORD_DETECTED',
        agent_role: 'senior_architect',
        display_name: 'Hestia'
      })
    })

    expect(store.selectedAgent).toBe('senior_architect')
    expect(store.isWakeWordTriggered).toBe(true)
    // hitlTargetAgents should remain unchanged by non-HITL wake words
    expect(store.hitlTargetAgents).toEqual(['innovator_architect'])

    store.stopAutoListen()
  })

  it('stops TTS when a SILENCE_VOICE_COMMAND is received via wakeWordWs', () => {
    const mockGetUserMedia = vi.fn().mockResolvedValue({
      getTracks: () => [{ stop: vi.fn() }]
    })
    Object.defineProperty(navigator, 'mediaDevices', {
      value: { getUserMedia: mockGetUserMedia },
      writable: true,
      configurable: true
    })

    const store = useDebateStore()
    store.connect()
    store.startAutoListen()

    const wwSocket = activeSockets[activeSockets.length - 1]
    expect(wwSocket).toBeDefined()

    // Simulate TTS playing
    store.isTtsPlaying = true

    // Receive SILENCE_VOICE_COMMAND from backend
    wwSocket!.onmessage?.({
      data: JSON.stringify({
        type: 'SILENCE_VOICE_COMMAND'
      })
    })

    expect(store.isTtsPlaying).toBe(false)
    store.stopAutoListen()
  })

  it('stops TTS when any HITL decision is submitted or refine voice command is triggered', () => {
    const mockGetUserMedia = vi.fn().mockResolvedValue({
      getTracks: () => [{ stop: vi.fn() }]
    })
    Object.defineProperty(navigator, 'mediaDevices', {
      value: { getUserMedia: mockGetUserMedia },
      writable: true,
      configurable: true
    })

    const store = useDebateStore()
    store.connect()
    store.startAutoListen()

    const wwSocket = activeSockets[activeSockets.length - 1]
    expect(wwSocket).toBeDefined()

    // 1. Calling submitHitlDecision stops ongoing TTS
    store.isTtsPlaying = true
    store.submitHitlDecision('approve')
    expect(store.isTtsPlaying).toBe(false)

    // 2. HITL refine voice command stops ongoing TTS
    store.isHitlRequired = true
    store.isTtsPlaying = true
    wwSocket!.onmessage?.({
      data: JSON.stringify({
        type: 'HITL_VOICE_COMMAND',
        command: 'refine'
      })
    })
    expect(store.isTtsPlaying).toBe(false)

    store.stopAutoListen()
  })

  it('tracks dynamic executionTrail live and resets on clearSession', () => {
    const store = useDebateStore()
    store.agents = [
      { role: 'supervisor', name: 'Atenea', state: 'STANDBY' },
      { role: 'nl_interpreter', name: 'Hermes', state: 'STANDBY' },
      { role: 'frontend_developer', name: 'Aracne', state: 'STANDBY' }
    ]

    expect(store.executionTrail).toEqual([])

    store.connect()
    store.isConnected = true
    store.startDebate('Requisito')
    expect(store.executionTrail).toEqual(['Atenea'])

    // Hermes starts
    store.handleSupervisorEvent({
      type: 'agent_started',
      role: 'nl_interpreter'
    })
    expect(store.executionTrail).toEqual(['Atenea', 'Hermes'])

    // Repeating agent_started for same agent doesn't duplicate consecutive entry
    store.handleSupervisorEvent({
      type: 'agent_started',
      role: 'nl_interpreter'
    })
    expect(store.executionTrail).toEqual(['Atenea', 'Hermes'])

    // Aracne starts
    store.handleSupervisorEvent({
      type: 'agent_started',
      role: 'frontend_developer'
    })
    expect(store.executionTrail).toEqual(['Atenea', 'Hermes', 'Aracne'])

    // Done event consolidates back to Atenea
    store.handleSupervisorEvent({
      type: 'done',
      role: 'supervisor',
      content: 'Debate finalizado.'
    })
    expect(store.executionTrail).toEqual(['Atenea', 'Hermes', 'Aracne', 'Atenea'])

    // Clear session empties the trail
    store.clearSession()
    expect(store.executionTrail).toEqual([])
  })

  it('fetches topology from backend endpoint /api/config/topology', async () => {
    const store = useDebateStore()
    const mockTopology = {
      supervisor: 'Atenea',
      interpreters: ['Hermes'],
      proposers: ['Ícaro', 'Hestia'],
      reviewers: ['Sphinx'],
      evaluators: ['Sphinx'],
      implementers: ['Aracne', 'Hefesto']
    }

    const originalFetch = global.fetch
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue(mockTopology)
    } as unknown as Response)

    try {
      await store.fetchTopology()
      expect(store.topology).toEqual(mockTopology)
    } finally {
      global.fetch = originalFetch
    }
  })
})


describe('cleanAgentMessageContent', () => {
  it('strips bracketed role tags', () => {
    expect(cleanAgentMessageContent('[nl_interpreter] Requisitos definidos.')).toBe('Requisitos definidos.')
    expect(cleanAgentMessageContent('[innovator_architect] Propuesta de vanguardia')).toBe('Propuesta de vanguardia')
    expect(cleanAgentMessageContent('[the_judge] Juicio emitido')).toBe('Juicio emitido')
  })

  it('strips initial markdown headers for agents and roles', () => {
    expect(cleanAgentMessageContent('## Interpretation\n\nRequisitos')).toBe('Requisitos')
    expect(cleanAgentMessageContent('## Ícaro\n\nSolución innovadora')).toBe('Solución innovadora')
    expect(cleanAgentMessageContent('## Sphinx\n\nEvaluación final')).toBe('Evaluación final')
  })

  it('strips composite bracket and header prefixes', () => {
    expect(cleanAgentMessageContent('[nl_interpreter] ## Interpretation\n\nRequisitos técnicos'))
      .toBe('Requisitos técnicos')
    expect(cleanAgentMessageContent('[innovator_architect] ## Ícaro\nOpción 1 y Opción 2'))
      .toBe('Opción 1 y Opción 2')
    expect(cleanAgentMessageContent('[the_judge] ## Sphinx\nDictamen'))
      .toBe('Dictamen')
  })

  it('preserves numbered markdown headings within content', () => {
    const text = '## 1. Enunciado / Intención Principal\nTexto de requisitos.'
    expect(cleanAgentMessageContent(text)).toBe(text)

    const text2 = '## 1. El Desafío (Visión de Ícaro)\nTexto descriptivo.'
    expect(cleanAgentMessageContent(text2)).toBe(text2)
  })

  it('handles empty or blank content gracefully', () => {
    expect(cleanAgentMessageContent('')).toBe('')
    expect(cleanAgentMessageContent('   ')).toBe('')
  })
})
