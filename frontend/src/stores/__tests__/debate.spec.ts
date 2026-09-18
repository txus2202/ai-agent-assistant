import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useDebateStore } from '../debate'

describe('useDebateStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
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
    // Mock WebSocket send
    store.ws = { send: () => {} } as any
    
    store.startDebate('test task')
    
    expect(store.isDebating).toBe(true)
    expect(store.messages).toHaveLength(1)
    expect(store.messages[0].content).toBe('test task')
    expect(store.messages[0].role).toBe('user')
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
