import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useConfigStore } from '../config'
import { configService } from '../../services/configService'
import { HttpError } from '../../services/httpClient'

describe('useConfigStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  it('initializes with default state', () => {
    const store = useConfigStore()
    expect(store.agentsConfig).toEqual([])
    expect(store.isLoading).toBe(false)
  })

  it('handles loadAgentsConfig by delegating to configService', async () => {
    const mockData = [
      { id: 'nl_interpreter', name: 'Nl Interpreter', provider: 'gemini', model_name: 'gemini-3.6-flash' },
    ]
    const loadSpy = vi.spyOn(configService, 'loadAgentsConfig').mockResolvedValue(mockData)

    const store = useConfigStore()
    await store.loadAgentsConfig()

    expect(store.agentsConfig).toHaveLength(1)
    expect(store.agentsConfig[0]!.provider).toBe('gemini')
    expect(loadSpy).toHaveBeenCalledTimes(1)
  })

  it('handles updateAgentConfig by delegating to configService and updating local state', async () => {
    const store = useConfigStore()
    store.agentsConfig = [
      { id: 'nl_interpreter', name: 'Nl Interpreter', provider: 'gemini', model_name: 'gemini-3.6-flash' },
    ]

    const updateSpy = vi.spyOn(configService, 'updateAgentConfig').mockResolvedValue({ ok: true })

    await store.updateAgentConfig('nl_interpreter', 'openai', 'gpt-4o')

    expect(updateSpy).toHaveBeenCalledWith('nl_interpreter', {
      provider: 'openai',
      model_name: 'gpt-4o',
    })
    expect(store.agentsConfig[0]!.provider).toBe('openai')
    expect(store.agentsConfig[0]!.model_name).toBe('gpt-4o')
  })

  it('handles updateAgentConfig with ragTopK and ragMinScore parameters', async () => {
    const store = useConfigStore()
    store.agentsConfig = [
      {
        id: 'caliope',
        name: 'Calíope',
        provider: 'gemini',
        model_name: 'gemini-2.5-flash',
        rag_top_k: 5,
        rag_min_score: 0.3,
      },
    ]

    const updateSpy = vi.spyOn(configService, 'updateAgentConfig').mockResolvedValue({ ok: true })

    await store.updateAgentConfig('caliope', 'gemini', 'gemini-2.5-flash', 0, 0.45)

    expect(updateSpy).toHaveBeenCalledWith('caliope', {
      provider: 'gemini',
      model_name: 'gemini-2.5-flash',
      rag_top_k: 0,
      rag_min_score: 0.45,
    })
    expect(store.agentsConfig[0]!.rag_top_k).toBe(0)
    expect(store.agentsConfig[0]!.rag_min_score).toBe(0.45)
  })

  it('handles loadProviders by using configService providers catalog', async () => {
    const mockProviders = [
      { id: 'gemini', name: 'Gemini', models: [{ id: 'gemini-1.5-flash', name: 'Gemini Flash' }] },
    ]
    vi.spyOn(configService, 'loadProviders').mockResolvedValue({
      providers: mockProviders,
      isProbing: false,
    })

    const store = useConfigStore()
    await store.loadProviders()

    expect(store.providers).toHaveLength(1)
    expect(store.providers[0]!.id).toBe('gemini')
  })

  it('schedules a silent re-fetch when isProbing is true', async () => {
    vi.useFakeTimers()
    const mockProviders = [
      { id: 'gemini', name: 'Gemini', models: [{ id: 'gemini-1.5-flash', name: 'Gemini Flash' }] },
    ]
    const loadProvidersSpy = vi
      .spyOn(configService, 'loadProviders')
      .mockResolvedValueOnce({ providers: mockProviders, isProbing: true })
      .mockResolvedValueOnce({ providers: mockProviders, isProbing: false })

    const store = useConfigStore()
    await store.loadProviders()

    expect(loadProvidersSpy).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(3500)

    expect(loadProvidersSpy).toHaveBeenCalledTimes(2)
  })

  it('handles loadProviders service error without throwing', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    vi.spyOn(configService, 'loadProviders').mockRejectedValue(new Error('Network error'))
    const store = useConfigStore()

    await store.loadProviders()
    expect(store.providers).toEqual([])
  })

  it('handles loadAgentsConfig error gracefully and resets isLoading', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    vi.spyOn(configService, 'loadAgentsConfig').mockRejectedValue(new Error('API failure'))
    const store = useConfigStore()

    await store.loadAgentsConfig()

    expect(store.isLoading).toBe(false)
    expect(store.agentsConfig).toEqual([])
  })

  it('does not update local state when updateAgentConfig fails with HttpError', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const store = useConfigStore()
    store.agentsConfig = [
      { id: 'supervisor', name: 'Supervisor', provider: 'gemini', model_name: 'gemini-1.5-pro' },
    ]

    vi.spyOn(configService, 'updateAgentConfig').mockRejectedValue(new HttpError('Server error', 500))

    await store.updateAgentConfig('supervisor', 'openai', 'gpt-4o')

    expect(store.agentsConfig[0]!.provider).toBe('gemini')
    expect(store.agentsConfig[0]!.model_name).toBe('gemini-1.5-pro')
  })

  it('handles updateAgentConfig network exception gracefully', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const store = useConfigStore()
    store.agentsConfig = [
      { id: 'supervisor', name: 'Supervisor', provider: 'gemini', model_name: 'gemini-1.5-pro' },
    ]

    vi.spyOn(configService, 'updateAgentConfig').mockRejectedValue(new Error('Network offline'))

    await store.updateAgentConfig('supervisor', 'openai', 'gpt-4o')

    expect(store.agentsConfig[0]!.provider).toBe('gemini')
  })
})
