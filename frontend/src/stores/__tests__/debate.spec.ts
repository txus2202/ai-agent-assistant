import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useDebateStore } from '../debate'

describe('useDebateStore', () => {
  let originalWebSocket: typeof WebSocket

  let mockSend: ReturnType<typeof vi.fn>

  beforeEach(() => {
    setActivePinia(createPinia())
    originalWebSocket = global.WebSocket
    mockSend = vi.fn()
    class MockWebSocket {
      readyState = WebSocket.OPEN
      send = mockSend
      close = vi.fn()
      addEventListener = vi.fn()
      removeEventListener = vi.fn()
      onopen = null
      onclose = null
      onmessage = null
      onerror = null
    }
    global.WebSocket = MockWebSocket as unknown as typeof WebSocket
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

  it('handles startAutoListen by creating a websocket', async () => {
    const store = useDebateStore()
    
    // Mock getUserMedia
    Object.defineProperty(global.navigator, 'mediaDevices', {
      value: {
        getUserMedia: vi.fn().mockResolvedValue({})
      },
      writable: true
    })

    // Mock AudioContext
    class MockAudioContext {
      createMediaStreamSource = vi.fn().mockReturnValue({ connect: vi.fn() })
      createScriptProcessor = vi.fn().mockReturnValue({
        connect: vi.fn(),
        onaudioprocess: null
      })
      destination = {}
      close = vi.fn().mockResolvedValue(undefined)
      resume = vi.fn().mockResolvedValue(undefined)
    }
    global.AudioContext = MockAudioContext as unknown as typeof AudioContext

    await store.startAutoListen()
    
    expect(store.isAutoListenEnabled).toBe(true)

    // Stop auto listen
    store.stopAutoListen()
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
})
