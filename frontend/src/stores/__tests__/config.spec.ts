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
    expect(store.agentsConfig[0]!.provider).toBe('gemini')
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

    expect(store.agentsConfig[0]!.provider).toBe('openai')
    expect(store.agentsConfig[0]!.model_name).toBe('gpt-4o')
  })

  it('handles loadProviders by fetching and filtering providers with models', async () => {
    const mockProviders = [
      { id: 'gemini', name: 'Gemini', models: [{ id: 'gemini-1.5-flash', name: 'Gemini Flash' }] },
      { id: 'empty_provider', name: 'Empty', models: [] }
    ]
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockProviders)
    })

    const store = useConfigStore()
    await store.loadProviders()

    expect(store.providers).toHaveLength(1)
    expect(store.providers[0]!.id).toBe('gemini')
  })

  it('handles loadProviders fetch error without throwing', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error'))
    const store = useConfigStore()

    await store.loadProviders()
    expect(store.providers).toEqual([])
  })

  it('handles loadAgentsConfig error gracefully and resets isLoading', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('API failure'))
    const store = useConfigStore()

    await store.loadAgentsConfig()

    expect(store.isLoading).toBe(false)
    expect(store.agentsConfig).toEqual([])
  })

  it('does not update local state when updateAgentConfig receives non-ok response', async () => {
    const store = useConfigStore()
    store.agentsConfig = [
      { id: 'supervisor', name: 'Supervisor', provider: 'gemini', model_name: 'gemini-1.5-pro' }
    ]

    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500
    })

    await store.updateAgentConfig('supervisor', 'openai', 'gpt-4o')

    expect(store.agentsConfig[0]!.provider).toBe('gemini')
    expect(store.agentsConfig[0]!.model_name).toBe('gemini-1.5-pro')
  })

  it('handles updateAgentConfig network exception gracefully', async () => {
    const store = useConfigStore()
    store.agentsConfig = [
      { id: 'supervisor', name: 'Supervisor', provider: 'gemini', model_name: 'gemini-1.5-pro' }
    ]

    global.fetch = vi.fn().mockRejectedValue(new Error('Network offline'))

    await store.updateAgentConfig('supervisor', 'openai', 'gpt-4o')

    expect(store.agentsConfig[0]!.provider).toBe('gemini')
  })
})
