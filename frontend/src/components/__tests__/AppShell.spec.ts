import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import AppShell from '../AppShell.vue'
import { useDebateStore } from '../../stores/debate'
import { AGENT_THEME, DEFAULT_AGENT_THEME } from '../../config/agentTheme'

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
          },
          EventStream: { template: '<div data-test="event-stream"></div>' }
        }
      }
    })
  }

  it('renders all main shell regions when initialized', () => {
    const wrapper = createWrapper()

    expect(wrapper.find('[data-test="app-header"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="chat-panel"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="particle-orb"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="event-stream"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('No checkpoints requiring attention')
  })

  it('computes default agent color when no agent is active or playing TTS', () => {
    const store = useDebateStore()
    store.agents = [
      { role: 'nl_interpreter', name: 'NL Interpreter', state: 'STANDBY' }
    ]
    store.activeTtsRole = null

    const wrapper = createWrapper()
    const orb = wrapper.findComponent({ name: 'ParticleOrb' })
    expect(orb.props('activeAgentColor')).toBe(DEFAULT_AGENT_THEME.hex)
  })

  it('computes active agent color based on currently active agent role', () => {
    const store = useDebateStore()
    store.agents = [
      { role: 'innovator_architect', name: 'Innovator Architect', state: 'ACTIVE' }
    ]

    const wrapper = createWrapper()
    const orb = wrapper.findComponent({ name: 'ParticleOrb' })
    expect(orb.props('activeAgentColor')).toBe(AGENT_THEME['innovator_architect']?.hex)
  })

  it('computes active agent color prioritizing activeTtsRole over active agent state', () => {
    const store = useDebateStore()
    store.agents = [
      { role: 'innovator_architect', name: 'Innovator Architect', state: 'ACTIVE' }
    ]
    store.activeTtsRole = 'the_judge'

    const wrapper = createWrapper()
    const orb = wrapper.findComponent({ name: 'ParticleOrb' })
    expect(orb.props('activeAgentColor')).toBe(AGENT_THEME['the_judge']?.hex)
  })

  it('handles HITL approve action', async () => {
    const store = useDebateStore()
    store.isHitlRequired = true
    store.submitHitlDecision = vi.fn()

    const wrapper = createWrapper()
    expect(wrapper.text()).toContain('Manual Override (HITL)')

    // Should find the approve button
    const approveBtn = wrapper.findAllComponents({ name: 'HITLActionButton' })
      .find(c => c.props('decision') === 'approve')
    expect(approveBtn).toBeDefined()

    await approveBtn!.find('button').trigger('click')
    expect(store.submitHitlDecision).toHaveBeenCalledWith('approve', '')
  })

  it('handles HITL refine flow with opening textarea, cancelling, and submitting feedback', async () => {
    const store = useDebateStore()
    store.isHitlRequired = true
    store.submitHitlDecision = vi.fn()

    const wrapper = createWrapper()

    // 1. Click Refine button to reveal feedback textarea
    const refineBtn = wrapper.findAllComponents({ name: 'HITLActionButton' })
      .find(c => c.props('decision') === 'refine')
    expect(refineBtn).toBeDefined()
    await refineBtn!.find('button').trigger('click')

    // Textarea is now revealed
    const textarea = wrapper.find('#hitl-feedback')
    expect(textarea.exists()).toBe(true)

    // Send button should be disabled when feedback is empty
    const sendBtn = wrapper.findAll('button').find(b => b.text().includes('SEND FEEDBACK'))
    expect(sendBtn?.attributes('disabled')).toBeDefined()

    // Cancel hides the textarea
    const cancelBtn = wrapper.findAll('button').find(b => b.text().includes('CANCEL'))
    await cancelBtn!.trigger('click')
    expect(wrapper.find('#hitl-feedback').exists()).toBe(false)

    // Re-open and type feedback
    const reopenRefineBtn = wrapper.findAllComponents({ name: 'HITLActionButton' })
      .find(c => c.props('decision') === 'refine')
    await reopenRefineBtn!.find('button').trigger('click')

    const feedbackInput = wrapper.find('#hitl-feedback')
    await feedbackInput.setValue('Please add security checks.')

    const submitFeedbackBtn = wrapper.findAll('button').find(b => b.text().includes('SEND FEEDBACK'))
    expect(submitFeedbackBtn?.attributes('disabled')).toBeUndefined()

    await submitFeedbackBtn!.trigger('click')
    expect(store.submitHitlDecision).toHaveBeenCalledWith('refine', 'Please add security checks.')
    expect(wrapper.find('#hitl-feedback').exists()).toBe(false)
  })
})
