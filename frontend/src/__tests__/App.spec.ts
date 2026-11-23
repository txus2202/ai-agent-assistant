import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import App from '../App.vue'
import { useDebateStore } from '../stores/debate'
import { useConfigStore } from '../stores/config'
import { useAuthStore } from '../stores/auth'

describe('App.vue', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([])
    })
  })

  it('does not fetch models or agents config while user is unauthenticated', async () => {
    const configStore = useConfigStore()
    const debateStore = useDebateStore()
    const authStore = useAuthStore()
    authStore.user = null

    configStore.loadProviders = vi.fn().mockResolvedValue(undefined)
    configStore.loadAgentsConfig = vi.fn().mockResolvedValue(undefined)
    debateStore.loadAgents = vi.fn().mockResolvedValue(undefined)

    mount(App, {
      global: {
        stubs: {
          'router-view': { template: '<div data-test="router-view-stub">Route View</div>' }
        }
      }
    })

    await flushPromises()

    expect(configStore.loadProviders).not.toHaveBeenCalled()
    expect(configStore.loadAgentsConfig).not.toHaveBeenCalled()
    expect(debateStore.loadAgents).not.toHaveBeenCalled()
  })

  it('renders loading state before agents are loaded and calls initialization on mount when authenticated', async () => {
    const configStore = useConfigStore()
    const debateStore = useDebateStore()
    const authStore = useAuthStore()
    authStore.user = {
      id: 'usr-1',
      username: 'admin',
      is_admin: true,
      is_active: true,
      created_at: '2026-11-10T00:00:00Z'
    }

    let resolveAgents: () => void = () => {}
    configStore.loadProviders = vi.fn().mockResolvedValue(undefined)
    configStore.loadAgentsConfig = vi.fn().mockResolvedValue(undefined)
    debateStore.loadAgents = vi.fn().mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          resolveAgents = () => {
            debateStore.isAgentsLoaded = true
            resolve()
          }
        })
    )

    const wrapper = mount(App, {
      global: {
        stubs: {
          'router-view': { template: '<div data-test="router-view-stub">Route View</div>' }
        }
      }
    })

    expect(wrapper.text()).toContain('INITIALIZING AI AGENT ASSISTANT...')
    expect(wrapper.find('[data-test="router-view-stub"]').exists()).toBe(false)

    resolveAgents()
    await flushPromises()

    expect(configStore.loadProviders).toHaveBeenCalled()
    expect(configStore.loadAgentsConfig).toHaveBeenCalled()
    expect(debateStore.loadAgents).toHaveBeenCalled()
  })

  it('renders router-view once agents are loaded', async () => {
    const debateStore = useDebateStore()
    debateStore.isAgentsLoaded = true

    const wrapper = mount(App, {
      global: {
        stubs: {
          'router-view': { template: '<div data-test="router-view-stub">Route View</div>' }
        }
      }
    })

    expect(wrapper.find('[data-test="router-view-stub"]').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('INITIALIZING AI AGENT ASSISTANT...')
  })

  it('updates document.title and loading text dynamically from store.projectName', async () => {
    const debateStore = useDebateStore()
    debateStore.topology = {
      project_name: 'PEPOTEZOTE',
      supervisor: 'Atenea',
      interpreters: [],
      proposers: [],
      reviewers: [],
      evaluators: [],
      implementers: []
    }
    const wrapper = mount(App, {
      global: {
        stubs: {
          'router-view': { template: '<div data-test="router-view-stub">Route View</div>' }
        }
      }
    })
    expect(wrapper.text()).toContain('INITIALIZING PEPOTEZOTE...')
    expect(document.title).toBe('PEPOTEZOTE')
  })

  it('renders BackendUnavailable component when backend is unavailable', async () => {
    const authStore = useAuthStore()
    authStore.isBackendAvailable = false
    authStore.errorMessage = 'No se ha podido conectar con el servidor backend.'

    const wrapper = mount(App, {
      global: {
        stubs: {
          'router-view': { template: '<div data-test="router-view-stub">Route View</div>' }
        }
      }
    })

    expect(wrapper.text()).toContain('Servidor Backend No Disponible')
    expect(wrapper.find('[data-test="router-view-stub"]').exists()).toBe(false)
  })

  it('logs out the user and redirects to /login instead of staying on blank screen when application initialization or agent loading fails', async () => {
    const configStore = useConfigStore()
    const debateStore = useDebateStore()
    const authStore = useAuthStore()
    authStore.user = {
      id: 'usr-1',
      username: 'admin',
      is_admin: true,
      is_active: true,
      created_at: '2026-11-10T00:00:00Z'
    }

    const logoutSpy = vi.spyOn(authStore, 'logout').mockImplementation(async () => {
      authStore.user = null
    })
    configStore.loadProviders = vi.fn().mockRejectedValue(new Error('Failed to load providers'))
    configStore.loadAgentsConfig = vi.fn().mockResolvedValue(undefined)
    debateStore.loadAgents = vi.fn().mockResolvedValue(undefined)

    mount(App, {
      global: {
        stubs: {
          'router-view': { template: '<div data-test="router-view-stub">Route View</div>' }
        }
      }
    })

    await flushPromises()

    expect(logoutSpy).toHaveBeenCalled()
    expect(authStore.user).toBeNull()
  })

  it('logs out the user and redirects to /login when a child route component throws a runtime error (onErrorCaptured)', async () => {
    const debateStore = useDebateStore()
    const authStore = useAuthStore()
    debateStore.isAgentsLoaded = true
    authStore.user = {
      id: 'usr-1',
      username: 'admin',
      is_admin: true,
      is_active: true,
      created_at: '2026-11-10T00:00:00Z'
    }

    const logoutSpy = vi.spyOn(authStore, 'logout').mockImplementation(async () => {
      authStore.user = null
    })

    const BrokenChild = {
      name: 'BrokenChild',
      setup() {
        throw new Error('Navigation render crash between App and History')
      },
      template: '<div>Broken</div>'
    }

    mount(App, {
      global: {
        stubs: {
          'router-view': BrokenChild
        }
      }
    })

    await flushPromises()

    expect(logoutSpy).toHaveBeenCalled()
    expect(authStore.user).toBeNull()
  })
})
