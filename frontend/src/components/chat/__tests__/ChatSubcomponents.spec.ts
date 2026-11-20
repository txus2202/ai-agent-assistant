import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ChatAgentSelector from '../ChatAgentSelector.vue'
import ChatHitlCard from '../ChatHitlCard.vue'
import ChatLearningBar from '../ChatLearningBar.vue'
import ChatPresentationCard from '../ChatPresentationCard.vue'

describe('Chat subcomponents', () => {
  it('ChatLearningBar emits learning, clear and file removal events', async () => {
    const file = new File(['hello'], 'notes.md')
    const wrapper = mount(ChatLearningBar, {
      props: {
        isLearningSession: false,
        canLearn: true,
        learningStatusMessage: '✅ Guardado en Vault',
        selectedFiles: [file],
      },
    })

    await wrapper.find('[data-test="learn-session-btn"]').trigger('click')
    expect(wrapper.emitted('learn-session')).toHaveLength(1)

    await wrapper.find('[data-test="remove-file-btn"]').trigger('click')
    expect(wrapper.emitted('remove-file')).toEqual([[0]])

    await wrapper.find('[data-test="clear-files-btn"]').trigger('click')
    expect(wrapper.emitted('clear-files')).toHaveLength(1)

    await wrapper.find('[data-test="learning-status-banner"] button').trigger('click')
    expect(wrapper.emitted('dismiss-learning-status')).toHaveLength(1)
  })

  it('ChatHitlCard emits target chip selection and HITL decision events', async () => {
    const wrapper = mount(ChatHitlCard, {
      props: {
        selectableAgents: [
          { value: 'senior_architect', label: 'Hestia', colorHex: '#00e5ff' },
        ],
        selectedTargets: ['senior_architect'],
        hasErrorRecovery: true,
      },
    })

    const retryBtn = wrapper.find('[data-test="hitl-retry-btn"]')
    expect(retryBtn.classes()).toContain('animate-pulse')
    await retryBtn.trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)

    await wrapper.find('[data-test="hitl-target-chip"]').trigger('click')
    expect(wrapper.emitted('toggle-target')).toEqual([['senior_architect']])

    await wrapper.find('[data-test="hitl-approve-btn"]').trigger('click')
    await wrapper.find('[data-test="hitl-consolidate-btn"]').trigger('click')
    await wrapper.find('[data-test="hitl-finish-btn"]').trigger('click')
    await wrapper.find('[data-test="hitl-refine-btn"]').trigger('click')
    await wrapper.find('[data-test="hitl-divert-btn"]').trigger('click')
    await wrapper.find('[data-test="hitl-reject-btn"]').trigger('click')

    expect(wrapper.emitted('approve')).toHaveLength(1)
    expect(wrapper.emitted('consolidate')).toHaveLength(1)
    expect(wrapper.emitted('finish')).toHaveLength(1)
    expect(wrapper.emitted('refine')).toHaveLength(1)
    expect(wrapper.emitted('divert')).toHaveLength(1)
    expect(wrapper.emitted('reject')).toHaveLength(1)
  })

  it('ChatAgentSelector toggles individual options and select-all cleanly', async () => {
    const wrapper = mount(ChatAgentSelector, {
      props: {
        agents: [
          { value: 'supervisor', label: 'Atenea' },
          { value: 'senior_architect', label: 'Hestia' },
        ],
        selectedAgents: ['supervisor'],
        disabled: false,
      },
    })

    await wrapper.find('[data-test="agent-dropdown-btn"]').trigger('click')
    const options = wrapper.findAll('[data-test="agent-option"]')
    expect(options).toHaveLength(2)

    await options[1]?.trigger('click')
    expect(wrapper.emitted('update:selectedAgents')).toEqual([[['senior_architect']]])
  })

  it('ChatPresentationCard emits copy, open, toggle-download and download format actions', async () => {
    const wrapper = mount(ChatPresentationCard, {
      props: {
        block: { type: 'presentation', content: '# Deck', title: 'Arquitectura', slideCount: 4 },
        cardKey: 100,
        agentName: 'Calíope',
        isCopied: false,
        isDownloadMenuOpen: true,
      },
    })

    await wrapper.find('[data-test="chat-presentation-copy-btn"]').trigger('click')
    expect(wrapper.emitted('copy')?.[0]?.[0]).toEqual({
      kind: 'presentation',
      content: '# Deck',
      cardKey: 100,
    })

    await wrapper.find('[data-test="chat-presentation-download-pptx-btn"]').trigger('click')
    expect(wrapper.emitted('download')?.[0]?.[0]).toEqual({
      kind: 'presentation-pptx',
      content: '# Deck',
      title: 'Arquitectura',
    })

    await wrapper.find('[data-test="chat-presentation-project-btn"]').trigger('click')
    expect(wrapper.emitted('open')?.[0]?.[0]).toMatchObject({
      kind: 'presentation',
      content: '# Deck',
    })
  })
})

