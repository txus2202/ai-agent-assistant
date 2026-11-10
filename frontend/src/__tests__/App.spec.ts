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

    configStore.loadProviders = vi.fn().mockResolvedValue(undefined)
    configStore.loadAgentsConfig = vi.fn().mockResolvedValue(undefined)
    debateStore.loadAgents = vi.fn().mockImplementation(() => {
      debateStore.isAgentsLoaded = false
    })

    const wrapper = mount(App, {
      global: {
        stubs: {
          'router-view': { template: '<div data-test="router-view-stub">Route View</div>' }
        }
      }
    })

    expect(wrapper.text()).toContain('INITIALIZING A.T.E.N.E.A...')
    expect(wrapper.find('[data-test="router-view-stub"]').exists()).toBe(false)

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
    expect(wrapper.text()).not.toContain('INITIALIZING A.T.E.N.E.A...')
  })
})
