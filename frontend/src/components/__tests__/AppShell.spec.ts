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

  const setActiveTabSpy = vi.fn()
  const resizeCanvasSpy = vi.fn()
  const toggleRecordingSpy = vi.fn()

  const createWrapper = () => {
    return mount(AppShell, {
      global: {
        stubs: {
          AppHeader: { template: '<div data-test="app-header"></div>' },
          ChatPanel: {
            name: 'ChatPanel',
            template: '<div data-test="chat-panel" @click="$emit(\'toggle-mic\')"></div>',
            methods: { onSubmit: vi.fn(), setActiveTab: setActiveTabSpy }
          },
          ParticleOrb: {
            name: 'ParticleOrb',
            template: '<div data-test="particle-orb" :data-color="activeAgentColor"></div>',
            props: ['activeAgentColor', 'isDebating'],
            methods: { resizeCanvas: resizeCanvasSpy, toggleRecording: toggleRecordingSpy }
          },
          ObservabilityPanel: {
            name: 'ObservabilityPanel',
            template: '<div data-test="observability-panel"></div>'
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

  it('switches mobile tabs via bottom navigation bar and syncs with ChatPanel and ParticleOrb', async () => {
    const wrapper = createWrapper()

    // Default mobile tab is 'chat'
    expect(wrapper.find('[data-test="shell-left-column"]').classes()).toContain('flex')
    expect(wrapper.find('[data-test="mobile-mini-orb-bar"]').exists()).toBe(true)

    // Switch to 'voice' (Voz 3D)
    await wrapper.find('[data-test="mobile-nav-voice"]').trigger('click')
    expect(wrapper.find('[data-test="shell-left-column"]').classes()).toContain('hidden')
    expect(wrapper.find('[data-test="shell-orb-column"]').classes()).toContain('flex')
    expect(resizeCanvasSpy).toHaveBeenCalled()

    // Switch to 'agents'
    await wrapper.find('[data-test="mobile-nav-agents"]').trigger('click')
    expect(wrapper.find('[data-test="shell-agents-column"]').classes()).toContain('flex')

    // Switch to 'telemetry'
    await wrapper.find('[data-test="mobile-nav-telemetry"]').trigger('click')
    expect(setActiveTabSpy).toHaveBeenCalledWith('observability')
    expect(wrapper.find('[data-test="shell-agents-column"]').classes()).toContain('flex')

    // Switch back to 'chat'
    await wrapper.find('[data-test="mobile-nav-chat"]').trigger('click')
    expect(setActiveTabSpy).toHaveBeenCalledWith('chat')
  })

  it('switches to 3D voice view when tapping the mobile contextual mini-orb bar and shows active agent summary', async () => {
    const store = useDebateStore()
    store.agents = [
      { role: 'diagrammer', name: 'Aracne', color_hex: '#ec4899', state: 'ACTIVE' }
    ]

    const wrapper = createWrapper()
    const miniOrbBar = wrapper.find('[data-test="mobile-mini-orb-bar"]')
    expect(miniOrbBar.text()).toContain('Aracne sintetizando...')

    await miniOrbBar.trigger('click')
    expect(wrapper.find('[data-test="shell-orb-column"]').classes()).toContain('flex')
  })

  it('switches tablet right column tabs between Orbe 3D, Agentes, and Telemetría', async () => {
    const wrapper = createWrapper()

    // Default tablet tab is 'orb'
    expect(wrapper.find('[data-test="shell-tablet-telemetry"]').exists()).toBe(false)

    // Switch to 'agents'
    await wrapper.find('[data-test="tablet-tab-agents"]').trigger('click')
    expect(wrapper.find('[data-test="shell-agents-column"]').classes()).toContain('md:flex')

    // Switch to 'telemetry'
    await wrapper.find('[data-test="tablet-tab-telemetry"]').trigger('click')
    expect(wrapper.find('[data-test="shell-tablet-telemetry"]').exists()).toBe(true)

    // Switch back to 'orb'
    await wrapper.find('[data-test="tablet-tab-orb"]').trigger('click')
    expect(wrapper.find('[data-test="shell-orb-column"]').classes()).toContain('md:flex')
  })

  it('triggers ParticleOrb toggleRecording when ChatPanel emits toggle-mic', async () => {
    const wrapper = createWrapper()
    await wrapper.find('[data-test="chat-panel"]').trigger('click')
    expect(toggleRecordingSpy).toHaveBeenCalled()
  })
})
