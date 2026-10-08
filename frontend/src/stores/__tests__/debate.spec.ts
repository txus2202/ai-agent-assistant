import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useDebateStore } from '../debate'

describe('useDebateStore', () => {
  let originalWebSocket: typeof WebSocket

  let mockSend: any

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
    global.WebSocket = MockWebSocket as any
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
    expect(store.agents[0].role).toBe('nl_interpreter')
    expect(store.agents[0].state).toBe('STANDBY')
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
    expect(store.messages[0].content).toBe('test task')
    expect(store.messages[0].role).toBe('user')
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
    global.AudioContext = MockAudioContext as any

    await store.startAutoListen()
    
    expect(store.isAutoListenEnabled).toBe(true)
  })
})
