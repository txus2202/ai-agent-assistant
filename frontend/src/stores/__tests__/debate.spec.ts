import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useDebateStore } from '../debate'

describe('useDebateStore', () => {
  let originalWebSocket: typeof WebSocket

  beforeEach(() => {
    setActivePinia(createPinia())
    originalWebSocket = global.WebSocket
    global.WebSocket = vi.fn().mockImplementation(function(this: any) {
      this.readyState = WebSocket.OPEN
      this.send = vi.fn()
      this.close = vi.fn()
      this.addEventListener = vi.fn()
      this.removeEventListener = vi.fn()
    }) as any
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
    
    // Set connected so it proceeds to send
    store.isConnected = true
    store.startDebate('test task')
    
    expect(store.isDebating).toBe(true)
    expect(store.messages).toHaveLength(1)
    expect(store.messages[0].content).toBe('test task')
    expect(store.messages[0].role).toBe('user')
    // We can verify send was called on the mocked ws
    expect(store.ws?.send).toHaveBeenCalledWith(JSON.stringify({ type: 'start', user_request: 'test task' }))
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
})
