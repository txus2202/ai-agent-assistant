import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useConfigStore } from '../config'

describe('useConfigStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('initializes with default state', () => {
    const store = useConfigStore()
    expect(store.agentsConfig).toEqual([])
    expect(store.isLoading).toBe(false)
  })

  it('handles loadAgentsConfig by fetching from API', async () => {
    const mockData = [
      { id: 'nl_interpreter', name: 'Nl Interpreter', provider: 'gemini', model_name: 'gemini-3.6-flash' }
    ]
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockData)
    })

    const store = useConfigStore()
    await store.loadAgentsConfig()

    expect(store.agentsConfig).toHaveLength(1)
    expect(store.agentsConfig[0].provider).toBe('gemini')
    expect(global.fetch).toHaveBeenCalledWith('/api/config/agents')
  })

  it('handles updateAgentConfig by making a PUT request and updating local state', async () => {
    const store = useConfigStore()
    store.agentsConfig = [
      { id: 'nl_interpreter', name: 'Nl Interpreter', provider: 'gemini', model_name: 'gemini-3.6-flash' }
    ]

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ ok: true })
    })

    await store.updateAgentConfig('nl_interpreter', 'openai', 'gpt-4o')

    expect(global.fetch).toHaveBeenCalledWith('/api/config/agents/nl_interpreter', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider: 'openai', model_name: 'gpt-4o' })
    })

    expect(store.agentsConfig[0].provider).toBe('openai')
    expect(store.agentsConfig[0].model_name).toBe('gpt-4o')
  })
})
