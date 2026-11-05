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
            props: ['activeAgentColor', 'isDebating', 'activeAgents'],
            methods: { resizeCanvas: resizeCanvasSpy, toggleRecording: toggleRecordingSpy }
          },
          ObservabilityPanel: {
            name: 'ObservabilityPanel',
            template: '<div data-test="observability-panel"></div>'
          },
          SoundBar: {
            name: 'SoundBar',
            template: '<div data-test="sound-bar" @click="$emit(\'open-voice\')"><button data-test="soundbar-view-switch" @click.stop="$emit(\'open-voice\')">3D &gt;</button></div>',
            props: ['activeAgentColor', 'isDebating', 'showViewSwitch', 'listenWakeWord'],
            methods: { toggleRecording: vi.fn() }
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

  it('computes default agent color when no agent is active or playing TTS (defaults to Atenea gold)', () => {
    const store = useDebateStore()
    store.agents = [
      { role: 'nl_interpreter', name: 'NL Interpreter', state: 'STANDBY' }
    ]
    store.activeTtsRole = null

    const wrapper = createWrapper()
    const orb = wrapper.findComponent({ name: 'ParticleOrb' })
    expect(orb.props('activeAgentColor')).toBe('#f59e0b')
  })

  it('keeps orb idle and active agents empty during HITL when TTS is silent', () => {
    const store = useDebateStore()
    store.isDebating = true
    store.isHitlRequired = true
    store.isTtsPlaying = false
    store.agents = [
      { role: 'nl_interpreter', name: 'Hermes', color_hex: '#00e5ff', state: 'COMPLETED' }
    ]

    const wrapper = createWrapper()
    const orb = wrapper.findComponent({ name: 'ParticleOrb' })
    expect(orb.props('isDebating')).toBe(false)
    expect(orb.props('activeAgents')).toEqual([])
  })

  it('always includes Atenea in activeAgents during an Atenea debate flow alongside delegated agents', () => {
    const store = useDebateStore()
    store.selectedAgent = 'supervisor'
    store.isDebating = true
    store.isHitlRequired = false
    store.agents = [
      { role: 'supervisor', name: 'Atenea', color_hex: '#f59e0b', state: 'STANDBY' },
      { role: 'nl_interpreter', name: 'Hermes', color_hex: '#00e5ff', state: 'ACTIVE' }
    ]

    const wrapper = createWrapper()
    const orb = wrapper.findComponent({ name: 'ParticleOrb' })
    const activeAgents = orb.props('activeAgents')
    expect(activeAgents).toHaveLength(2)
    expect(activeAgents[0].name).toBe('Atenea')
    expect(activeAgents[0].color).toBe('#f59e0b')
    expect(activeAgents[1].name).toBe('Hermes')
    expect(activeAgents[1].color).toBe('#00e5ff')
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
    expect(wrapper.find('[data-test="mobile-sound-bar"]').exists()).toBe(true)

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

  it('renders mobile sound bar without 3D switch button in mobile chat view', () => {
    const wrapper = createWrapper()
    const soundBar = wrapper.findComponent({ name: 'SoundBar' })
    expect(soundBar.exists()).toBe(true)
    expect(soundBar.props('showViewSwitch')).toBe(false)
  })

  it('configures Hero Centerpiece layout on tablet with top full-width orb and split bottom chat and agents', () => {
    const wrapper = createWrapper()
    const grid = wrapper.find('[data-test="shell-workspace-grid"]')
    expect(grid.classes()).toContain('md:grid')
    expect(grid.classes()).toContain('md:grid-cols-2')
    expect(grid.classes()).toContain('xl:flex')
    expect(grid.classes()).toContain('xl:flex-row')

    const orbCol = wrapper.find('[data-test="shell-orb-column"]')
    expect(orbCol.classes()).toContain('md:col-span-2')
    expect(orbCol.classes()).toContain('md:row-start-1')
    expect(orbCol.classes()).toContain('xl:flex-1')

    const chatCol = wrapper.find('[data-test="shell-left-column"]')
    expect(chatCol.classes()).toContain('md:col-span-1')
    expect(chatCol.classes()).toContain('md:row-start-2')
    expect(chatCol.classes()).toContain('xl:w-[380px]')

    const agentsCol = wrapper.find('[data-test="shell-agents-column"]')
    expect(agentsCol.classes()).toContain('md:col-span-1')
    expect(agentsCol.classes()).toContain('md:row-start-2')
    expect(agentsCol.classes()).toContain('xl:w-[380px]')
  })

  it('triggers ParticleOrb toggleRecording when ChatPanel emits toggle-mic', async () => {
    const wrapper = createWrapper()
    await wrapper.find('[data-test="chat-panel"]').trigger('click')
    expect(toggleRecordingSpy).toHaveBeenCalled()
  })
})
