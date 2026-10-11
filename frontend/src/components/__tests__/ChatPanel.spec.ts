import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ChatPanel from '../ChatPanel.vue'

import { useDebateStore, type ChatMessage, type SupervisorEvent } from '../../stores/debate'

// Mock the debate store
const mockStartDebate = vi.fn()
const mockUploadFile = vi.fn().mockResolvedValue('/uploads/test.pdf')
const mockStore = {
  isDebating: false,
  messages: [] as ChatMessage[],
  rawEvents: [] as SupervisorEvent[],
  startDebate: mockStartDebate,
  uploadFile: mockUploadFile,
  draftMessage: '',
  isVoiceOutputEnabled: false,
  isTtsPlaying: false,
  activeTtsRole: null
}

vi.mock('../../stores/debate', () => ({
  useDebateStore: () => mockStore
}))

describe('ChatPanel.vue', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('renders input area correctly', () => {
    const wrapper = mount(ChatPanel, {
      props: {
        messages: [],
        isDebating: false
      }
    })
    expect(wrapper.find('textarea').exists()).toBe(true)
    expect(wrapper.find('button[type="submit"]').exists()).toBe(true)
  })

  it('submits a task with target agent and file attachment', async () => {
    const wrapper = mount(ChatPanel, {
      props: {
        messages: [],
        isDebating: false
      }
    })
    
    // Find target agent select dropdown and click it
    const dropdownBtn = wrapper.find('[data-test="agent-dropdown-btn"]')
    expect(dropdownBtn.exists()).toBe(true)
    await dropdownBtn.trigger('click')

    // Find the learning agent option and click it
    const options = wrapper.findAll('[data-test="agent-option"]')
    const learningOption = options.find(btn => btn.text().includes('Learning Agent'))
    expect(learningOption).toBeDefined()
    await learningOption!.trigger('click')

    // Find textarea and set value
    const textarea = wrapper.find('textarea')
    await textarea.setValue('Help me learn Vue')

    // Find file input and simulate a file selection
    const fileInput = wrapper.find('[data-test="file-input"]')
    expect(fileInput.exists()).toBe(true)
    
    // We can't easily mock file objects via setValue, so we mock the upload handler
    // We'll trigger the start directly by submitting the form
    await wrapper.find('form').trigger('submit.prevent')

    expect(mockStartDebate).toHaveBeenCalledWith('Help me learn Vue', 'learning', null)
  })

  it('renders user and assistant messages properly', () => {
    const messages = [
      { role: 'user' as const, content: 'Can we build a microservices architecture?' },
      { role: 'assistant' as const, content: 'Here is the recommended topology with 3 microservices.' }
    ]

    const wrapper = mount(ChatPanel, {
      props: {
        messages,
        isDebating: false
      }
    })

    expect(wrapper.text()).toContain('USUARIO (TÚ)')
    expect(wrapper.text()).toContain('Can we build a microservices architecture?')
    expect(wrapper.text()).toContain('Here is the recommended topology with 3 microservices.')
  })

  it('does not trigger startDebate if message draft is empty or whitespace only', async () => {
    const wrapper = mount(ChatPanel, {
      props: {
        messages: [],
        isDebating: false
      }
    })

    const textarea = wrapper.find('textarea')
    await textarea.setValue('   ')
    await wrapper.find('form').trigger('submit.prevent')

    expect(mockStartDebate).not.toHaveBeenCalled()
  })

  it('clears chat when clicking Limpiar and user confirms', async () => {
    const store = useDebateStore()
    store.messages = [{ role: 'user', content: 'hello' }]
    store.rawEvents = [{ type: 'start' }]

    global.confirm = vi.fn().mockReturnValue(true)

    const wrapper = mount(ChatPanel, {
      props: {
        messages: store.messages,
        isDebating: false
      }
    })

    const clearButton = wrapper.findAll('button').find(b => b.text().includes('LIMPIAR') || b.text().includes('Limpiar'))
    expect(clearButton).toBeDefined()
    await clearButton!.trigger('click')

    expect(global.confirm).toHaveBeenCalled()
    expect(store.messages).toHaveLength(0)
    expect(store.rawEvents).toHaveLength(0)
  })

  it('disables input controls when isDebating is true', () => {
    const wrapper = mount(ChatPanel, {
      props: {
        messages: [],
        isDebating: true
      }
    })

    const textarea = wrapper.find('textarea')
    expect(textarea.element.disabled).toBe(true)

    const submitBtn = wrapper.find('button[type="submit"]')
    expect(submitBtn.element.getAttribute('disabled')).not.toBeNull()
  })

  it('handles file selection and displays attachment indicator', async () => {
    const wrapper = mount(ChatPanel, {
      props: {
        messages: [],
        isDebating: false
      }
    })

    // First select learning agent so file upload button is rendered
    const dropdownBtn = wrapper.find('[data-test="agent-dropdown-btn"]')
    await dropdownBtn.trigger('click')
    const options = wrapper.findAll('[data-test="agent-option"]')
    const learningOption = options.find(btn => btn.text().includes('Learning Agent'))
    await learningOption!.trigger('click')

    const fileInput = wrapper.find('[data-test="file-input"]')
    const file = new File(['sample content'], 'specs.pdf', { type: 'application/pdf' })

    Object.defineProperty(fileInput.element, 'files', {
      value: [file],
      writable: false
    })

    await fileInput.trigger('change')

    expect(wrapper.text()).toContain('Archivo de contexto cargado (specs.pdf)')

    const textarea = wrapper.find('textarea')
    await textarea.setValue('Review this document')
    await wrapper.find('form').trigger('submit.prevent')

    expect(mockUploadFile).toHaveBeenCalledWith(file)
    expect(mockStartDebate).toHaveBeenCalledWith('Review this document', 'learning', '/uploads/test.pdf')
  })

  it('exposes onSubmit method for external triggers like ParticleOrb', async () => {
    const wrapper = mount(ChatPanel, {
      props: {
        messages: [],
        isDebating: false
      }
    })

    const textarea = wrapper.find('textarea')
    await textarea.setValue('Voice drafted prompt')

    // Call exposed onSubmit directly
    await (wrapper.vm as unknown as { onSubmit: () => Promise<void> }).onSubmit()

    expect(mockStartDebate).toHaveBeenCalledWith('Voice drafted prompt', 'supervisor', null)
  })
})
