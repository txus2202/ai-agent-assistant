import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import TopologyView from '../TopologyView.vue'
import { configService, type DebateTopology } from '../../services/configService'
import { useDebateStore } from '../../stores/debate'

const pushMock = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: pushMock,
  }),
  useRoute: () => ({
    path: '/topology',
  }),
}))

const sampleDefaultTopology = (): DebateTopology => ({
  project_name: 'A.T.E.N.E.A.',
  project_description: 'Asistente Técnica y Evaluadora de Nuevas Estructuras y Arquitecturas',
  supervisor: 'Atenea',
  interpreters: ['Hermes'],
  proposers: ['Ícaro', 'Hestia'],
  reviewers: ['Sphinx'],
  evaluators: ['Sphinx'],
  implementers: ['Aracne', 'Hefesto'],
  review_rounds: 1,
  is_customized: false,
  supervisor_agent: {
    id: 'supervisor',
    name: 'Atenea',
    description: 'Orquestadora estratégica del consejo técnico.',
    color_hex: '#f59e0b',
  },
  eligible_agents: [
    {
      id: 'nl_interpreter',
      name: 'Hermes',
      description: 'Traduce peticiones ambiguas en especificaciones técnicas estructuradas.',
      color_hex: '#06b6d4',
      uses_rag: false,
      supports_hitl: true,
    },
    {
      id: 'innovator',
      name: 'Ícaro',
      description: 'Arquitecto innovador y audaz con soluciones cloud-native.',
      color_hex: '#22c55e',
      uses_rag: true,
      supports_hitl: true,
    },
    {
      id: 'senior_architect',
      name: 'Hestia',
      description: 'Arquitecta senior que asegura estabilidad empresarial y Clean Architecture.',
      color_hex: '#00ff9d',
      uses_rag: true,
      supports_hitl: true,
    },
    {
      id: 'the_judge',
      name: 'Sphinx',
      description: 'Auditora implacable que detecta vulnerabilidades y cuellos de botella.',
      color_hex: '#ef4444',
      uses_rag: true,
      supports_hitl: true,
    },
    {
      id: 'devops_secops',
      name: 'Hefesto',
      description: 'Especialista DevSecOps que forja pipelines seguros y despliegues robustos.',
      color_hex: '#ff8800',
      uses_rag: true,
      supports_hitl: true,
    },
    {
      id: 'diagrammer',
      name: 'Aracne',
      description: 'Tejedora maestra de diagramas interactivos en Mermaid.js.',
      color_hex: '#b347ff',
      uses_rag: true,
      supports_hitl: true,
    },
    {
      id: 'dedalo',
      name: 'Dédalo',
      description: 'Desarrollador full-stack y maestro artesano del software con Clean Code.',
      color_hex: '#cc7800',
      uses_rag: false,
      supports_hitl: true,
    },
  ],
})

describe('TopologyView.vue', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    pushMock.mockReset()
  })

  afterEach(async () => {
    await flushPromises()
    vi.restoreAllMocks()
  })

  it('renders only assigned AgentCards per phase with full descriptions instead of repeating all agents', async () => {
    vi.spyOn(configService, 'getTopology').mockResolvedValue(sampleDefaultTopology())

    const wrapper = mount(TopologyView)
    await flushPromises()

    expect(wrapper.find('[data-test="topology-status-badge"]').text()).toContain('Por Defecto')
    const supCard = wrapper.find('[data-test="topology-supervisor-card"]')
    expect(supCard.exists()).toBe(true)
    expect(supCard.text()).toContain('Atenea')
    expect(supCard.find('input').exists()).toBe(false)

    // Phase 1 (interpreters) only shows Hermes with its description, NOT Hefesto or Dédalo
    const phaseInterpreters = wrapper.find('[data-test="phase-section-interpreters"]')
    expect(phaseInterpreters.text()).toContain('Hermes')
    expect(phaseInterpreters.text()).toContain('especificaciones técnicas estructuradas')
    expect(phaseInterpreters.text()).not.toContain('Hefesto')
    expect(phaseInterpreters.text()).not.toContain('Dédalo')

    // Phase 2A (proposers) only shows Ícaro and Hestia with their descriptions
    const phaseProposers = wrapper.find('[data-test="phase-section-proposers"]')
    expect(phaseProposers.text()).toContain('Ícaro')
    expect(phaseProposers.text()).toContain('Hestia')
    expect(phaseProposers.text()).toContain('estabilidad empresarial')
    expect(phaseProposers.text()).not.toContain('Hefesto')
  })

  it('removes an assigned agent and adds a new specialist via the AgentCard picker modal, then saves', async () => {
    const initial = sampleDefaultTopology()
    const savedResponse: DebateTopology = {
      ...initial,
      proposers: ['Hestia', 'Hefesto'],
      review_rounds: 3,
      is_customized: true,
    }
    vi.spyOn(configService, 'getTopology').mockResolvedValue(initial)
    const updateSpy = vi.spyOn(configService, 'updateTopology').mockResolvedValue(savedResponse)
    const debateStore = useDebateStore()
    const loadAgentsSpy = vi.spyOn(debateStore, 'loadAgents').mockResolvedValue()

    const wrapper = mount(TopologyView)
    await flushPromises()

    // 1. Remove Ícaro directly from Phase 2A (proposers) card
    await wrapper.find('[data-test="remove-proposers-innovator"]').trigger('click')
    expect(wrapper.find('[data-test="phase-section-proposers"]').text()).not.toContain('Ícaro')

    // 2. Open specialist picker modal for proposers
    await wrapper.find('[data-test="open-picker-proposers"]').trigger('click')
    const dialog = wrapper.find('[data-test="specialist-picker-dialog"]')
    expect(dialog.attributes('open')).toBeDefined()
    expect(dialog.text()).toContain('Hefesto')
    expect(dialog.text()).toContain('forja pipelines seguros')

    // 3. Add Hefesto from inside the picker modal
    await wrapper.find('[data-test="picker-toggle-devops_secops"]').trigger('click')
    await wrapper.find('[data-test="picker-close-btn"]').trigger('click')
    expect(wrapper.find('[data-test="phase-section-proposers"]').text()).toContain('Hefesto')

    // 4. Set review_rounds = 3 and save
    await wrapper.find('#topology-review-rounds').setValue('3')
    await wrapper.find('[data-test="topology-main-form"]').trigger('submit.prevent')
    await flushPromises()

    expect(updateSpy).toHaveBeenCalledWith({
      interpreters: ['Hermes'],
      proposers: ['Hestia', 'Hefesto'],
      reviewers: ['Sphinx'],
      evaluators: ['Sphinx'],
      implementers: ['Aracne', 'Hefesto'],
      review_rounds: 3,
    })
    expect(wrapper.find('[data-test="topology-status-badge"]').text()).toContain('Personalizada')
    expect(loadAgentsSpy).toHaveBeenCalled()
  })

  it('blocks saving and shows alert when all execution phases are emptied', async () => {
    const minimal: DebateTopology = {
      ...sampleDefaultTopology(),
      interpreters: [],
      proposers: ['Hestia'],
      reviewers: ['Sphinx'],
      evaluators: [],
      implementers: [],
    }
    vi.spyOn(configService, 'getTopology').mockResolvedValue(minimal)
    const updateSpy = vi.spyOn(configService, 'updateTopology')

    const wrapper = mount(TopologyView)
    await flushPromises()

    await wrapper.find('[data-test="remove-proposers-senior_architect"]').trigger('click')
    expect(wrapper.find('[data-test="empty-slot-proposers"]').exists()).toBe(true)

    await wrapper.find('[data-test="topology-main-form"]').trigger('submit.prevent')
    await flushPromises()

    expect(updateSpy).not.toHaveBeenCalled()
    expect(wrapper.find('[role="alert"]').exists()).toBe(true)
  })

  it('resets customized topology back to canonical defaults via DELETE', async () => {
    const customized: DebateTopology = {
      ...sampleDefaultTopology(),
      proposers: ['Hefesto'],
      review_rounds: 4,
      is_customized: true,
    }
    const restored = sampleDefaultTopology()
    vi.spyOn(configService, 'getTopology').mockResolvedValue(customized)
    const resetSpy = vi.spyOn(configService, 'resetTopology').mockResolvedValue(restored)
    const debateStore = useDebateStore()
    const loadAgentsSpy = vi.spyOn(debateStore, 'loadAgents').mockResolvedValue()

    const wrapper = mount(TopologyView)
    await flushPromises()

    expect(wrapper.find('[data-test="topology-status-badge"]').text()).toContain('Personalizada')

    await wrapper.find('[data-test="topology-reset-btn"]').trigger('click')
    await flushPromises()

    expect(resetSpy).toHaveBeenCalledOnce()
    expect(wrapper.find('[data-test="topology-status-badge"]').text()).toContain('Por Defecto')
    expect(wrapper.find<HTMLInputElement>('#topology-review-rounds').element.value).toBe('1')
    expect(loadAgentsSpy).toHaveBeenCalled()
  })

  it('navigates back to home when clicking the back button', async () => {
    vi.spyOn(configService, 'getTopology').mockResolvedValue(sampleDefaultTopology())
    const wrapper = mount(TopologyView)
    await flushPromises()

    await wrapper.find('[data-test="topology-back-btn"]').trigger('click')
    expect(pushMock).toHaveBeenCalledWith('/')
  })
})
