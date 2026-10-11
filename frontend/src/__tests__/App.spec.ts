import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import App from '../App.vue'
import { useDebateStore } from '../stores/debate'
import { useConfigStore } from '../stores/config'

describe('App.vue', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([])
    })
  })

  it('renders loading state before agents are loaded and calls initialization on mount', async () => {
    const configStore = useConfigStore()
    const debateStore = useDebateStore()

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
