import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import AppShell from '../AppShell.vue'
import { useDebateStore } from '../../stores/debate'

// Mock fetch for AppHeader and others
global.fetch = vi.fn().mockResolvedValue({
  ok: true,
  json: () => Promise.resolve([])
})

describe('AppShell.vue', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(async () => {
    await flushPromises()
    vi.restoreAllMocks()
  })

  const createWrapper = () => {
    return mount(AppShell, {
      global: {
        stubs: {
          AppHeader: { template: '<div data-test="app-header"></div>' },
          ChatPanel: {
            template: '<div data-test="chat-panel"></div>',
            methods: { onSubmit: vi.fn() }
          },
          ParticleOrb: {
            name: 'ParticleOrb',
            template: '<div data-test="particle-orb" :data-color="activeAgentColor"></div>',
            props: ['activeAgentColor', 'isDebating']
          }
        }
      }
    })
  }

  it('renders all main shell regions when initialized', () => {
    const wrapper = createWrapper()

    expect(wrapper.find('[data-test="app-header"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="chat-panel"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="particle-orb"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Consejo en espera')
  })

  it('computes default agent color when no agent is active or playing TTS', () => {
    const store = useDebateStore()
    store.agents = [
      { role: 'nl_interpreter', name: 'NL Interpreter', state: 'STANDBY' }
    ]
    store.activeTtsRole = null

    const wrapper = createWrapper()
    const orb = wrapper.findComponent({ name: 'ParticleOrb' })
    expect(orb.props('activeAgentColor')).toBe('#00e5ff')
  })

  it('computes active agent color based on currently active agent color_hex', () => {
    const store = useDebateStore()
    store.agents = [
      { role: 'innovator_architect', name: 'Innovator Architect', color_hex: '#22c55e', state: 'ACTIVE' }
    ]

    const wrapper = createWrapper()
    const orb = wrapper.findComponent({ name: 'ParticleOrb' })
    expect(orb.props('activeAgentColor')).toBe('#22c55e')
  })

  it('computes active agent color prioritizing activeTtsRole over active agent state', () => {
    const store = useDebateStore()
    store.agents = [
      { role: 'innovator_architect', name: 'Innovator Architect', color_hex: '#22c55e', state: 'ACTIVE' },
      { role: 'the_judge', name: 'The Judge', color_hex: '#ef4444', state: 'STANDBY' }
    ]
    store.activeTtsRole = 'the_judge'

    const wrapper = createWrapper()
    const orb = wrapper.findComponent({ name: 'ParticleOrb' })
    expect(orb.props('activeAgentColor')).toBe('#ef4444')
  })

  it('computes supervisor color when activeTtsRole is supervisor', () => {
    const store = useDebateStore()
    store.agents = [
      { role: 'supervisor', name: 'Supervisor', color_hex: '#f59e0b', state: 'STANDBY' }
    ]
    store.activeTtsRole = 'supervisor'

    const wrapper = createWrapper()
    const orb = wrapper.findComponent({ name: 'ParticleOrb' })
    expect(orb.props('activeAgentColor')).toBe('#f59e0b')
  })

  it('computes normalized role color when activeTtsRole uses short name innovator', () => {
    const store = useDebateStore()
    store.agents = [
      { role: 'innovator_architect', name: 'Innovator Architect', color_hex: '#22c55e', state: 'STANDBY' }
    ]
    store.activeTtsRole = 'innovator'

    const wrapper = createWrapper()
    const orb = wrapper.findComponent({ name: 'ParticleOrb' })
    expect(orb.props('activeAgentColor')).toBe('#22c55e')
  })

  it('displays active council status when debate is running', () => {
    const store = useDebateStore()
    store.isDebating = true

    const wrapper = createWrapper()
    expect(wrapper.text()).toContain('Debate en curso')
  })

  it('displays HITL Activo badge in council panel when HITL is required', () => {
    const store = useDebateStore()
    store.isHitlRequired = true

    const wrapper = createWrapper()
    expect(wrapper.text()).toContain('HITL Activo')
  })
})
