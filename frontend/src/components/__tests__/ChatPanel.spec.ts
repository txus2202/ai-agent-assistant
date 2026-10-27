import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ChatPanel from '../ChatPanel.vue'

import { useDebateStore, type ChatMessage, type SupervisorEvent } from '../../stores/debate'

// Mock the debate store
const mockStartDebate = vi.fn()
const mockUploadFile = vi.fn().mockResolvedValue('/uploads/test.pdf')
const mockSubmitHitlDecision = vi.fn()
const mockStore = {
  isDebating: false,
  isHitlRequired: false,
  submitHitlDecision: mockSubmitHitlDecision,
  messages: [] as ChatMessage[],
  rawEvents: [] as SupervisorEvent[],
  agents: [
    { role: 'nl_interpreter', name: 'NL Interpreter', state: 'STANDBY', color_hex: '#00e5ff' },
    { role: 'learning', name: 'Learning Agent', state: 'STANDBY', color_hex: '#1d4ed8' },
    { role: 'diagrammer', name: 'Aracne', state: 'STANDBY', color_hex: '#ec4899' }
  ],
  startDebate: mockStartDebate,
  uploadFile: mockUploadFile,
  draftMessage: '',
  isVoiceOutputEnabled: false,
  isTtsPlaying: false,
  activeTtsRole: null as string | null,
  selectedAgent: 'supervisor',
  playTtsAudioChunk: vi.fn(),
  stopTts: vi.fn(),
  unlockAudioContext: vi.fn(),
  clearSession: vi.fn(() => {
    mockStore.messages.splice(0, mockStore.messages.length)
    mockStore.rawEvents.splice(0, mockStore.rawEvents.length)
  })
}

vi.mock('../../stores/debate', () => ({
  useDebateStore: () => mockStore
}))

describe('ChatPanel.vue', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockStore.selectedAgent = 'supervisor'
    Element.prototype.scrollIntoView = vi.fn()
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

  it('closes agent dropdown when clicking outside', async () => {
    const wrapper = mount(ChatPanel, {
      props: {
        messages: [],
        isDebating: false
      }
    })

    const dropdownBtn = wrapper.find('[data-test="agent-dropdown-btn"]')
    await dropdownBtn.trigger('click')
    expect(wrapper.find('[data-test="agent-option"]').exists()).toBe(true)

    // Simulate clicking outside
    document.dispatchEvent(new MouseEvent('click'))
    await wrapper.vm.$nextTick()

    expect(wrapper.find('[data-test="agent-option"]').exists()).toBe(false)
  })

  it('handles file upload error by alerting the user and halting debate start', async () => {
    mockUploadFile.mockRejectedValueOnce(new Error('File rejected'))
    global.alert = vi.fn()
    vi.spyOn(console, 'error').mockImplementation(() => {})

    const wrapper = mount(ChatPanel, {
      props: {
        messages: [],
        isDebating: false
      }
    })

    const dropdownBtn = wrapper.find('[data-test="agent-dropdown-btn"]')
    await dropdownBtn.trigger('click')
    const learningOption = wrapper.findAll('[data-test="agent-option"]').find(b => b.text().includes('Learning Agent'))
    await learningOption!.trigger('click')

    const fileInput = wrapper.find('[data-test="file-input"]')
    const file = new File(['content'], 'test.pdf')
    Object.defineProperty(fileInput.element, 'files', { value: [file], writable: false })
    await fileInput.trigger('change')

    const textarea = wrapper.find('textarea')
    await textarea.setValue('Help with file')
    await wrapper.find('form').trigger('submit.prevent')

    expect(global.alert).toHaveBeenCalledWith('Error uploading file. Please try again.')
    expect(mockStartDebate).not.toHaveBeenCalled()
  })

  it('triggers voice synthesis when a new assistant message arrives and voice output is enabled', async () => {
    mockStore.isVoiceOutputEnabled = true
    mockStore.playTtsAudioChunk = vi.fn().mockResolvedValue(undefined)
    mockStore.stopTts = vi.fn()

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      arrayBuffer: () => Promise.resolve(new ArrayBuffer(8))
    })

    const wrapper = mount(ChatPanel, {
      props: {
        messages: [],
        isDebating: false
      }
    })

    await wrapper.setProps({
      messages: [
        { role: 'assistant', content: '[senior_architect] System architecture approved. Ready for deployment.' }
      ]
    })

    expect(mockStore.isTtsPlaying).toBe(true)
    expect(mockStore.activeTtsRole).toBe('senior_architect')
    expect(global.fetch).toHaveBeenCalledWith('/api/audio/synthesize', expect.any(Object))
  })

  it('renders Silenciar button when TTS is playing and stops TTS on click', async () => {
    mockStore.isTtsPlaying = true
    const stopTtsSpy = vi.fn()
    mockStore.stopTts = stopTtsSpy

    const wrapper = mount(ChatPanel, {
      props: {
        messages: [
          { role: 'assistant', content: 'Assistant speech here', agentName: 'SUPERVISOR AGENT' }
        ],
        isDebating: false
      }
    })

    const muteBtn = wrapper.find('button[title="Detener lectura de este mensaje"]')
    expect(muteBtn.exists()).toBe(true)
    await muteBtn.trigger('click')
    expect(stopTtsSpy).toHaveBeenCalled()
  })

  it('unlocks audio context on submit when voice output is enabled', async () => {
    mockStore.isVoiceOutputEnabled = true
    const unlockSpy = vi.fn()
    mockStore.unlockAudioContext = unlockSpy

    const wrapper = mount(ChatPanel, {
      props: { messages: [], isDebating: false }
    })

    const textarea = wrapper.find('textarea')
    await textarea.setValue('Prompt with voice enabled')
    await wrapper.find('form').trigger('submit.prevent')

    expect(unlockSpy).toHaveBeenCalled()
  })

  it('switches to observability tab and displays ObservabilityPanel', async () => {
    const wrapper = mount(ChatPanel, {
      props: { messages: [], isDebating: false }
    })

    const obsTabBtn = wrapper.find('[data-test="tab-observability"]')
    expect(obsTabBtn.exists()).toBe(true)

    await obsTabBtn.trigger('click')

    expect(wrapper.text()).toContain('SYSTEM OBSERVABILITY')
    expect(wrapper.find('[data-test="tab-observability"]').classes()).toContain('text-neon-cyan')
  })

  it('renders integrated HITL card when isHitlRequired is true', () => {
    mockStore.isHitlRequired = true
    const wrapper = mount(ChatPanel, {
      props: { messages: [], isDebating: true }
    })

    expect(wrapper.find('[data-test="hitl-chat-card"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Punto de Control (HITL)')
    expect(wrapper.find('[data-test="hitl-approve-btn"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="hitl-reject-btn"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="hitl-refine-btn"]').exists()).toBe(true)
    expect(wrapper.find('textarea').attributes('placeholder')).toContain('instrucciones de refinamiento')
  })

  it('handles HITL approve action with target agents', async () => {
    mockStore.isHitlRequired = true
    const wrapper = mount(ChatPanel, {
      props: { messages: [], isDebating: true }
    })

    // Click a target chip (e.g. Aracne / diagrammer)
    const chips = wrapper.findAll('[data-test="hitl-target-chip"]')
    const aracneChip = chips.find(c => c.text().includes('Aracne'))
    if (aracneChip) {
      await aracneChip.trigger('click')
    }

    const approveBtn = wrapper.find('[data-test="hitl-approve-btn"]')
    await approveBtn.trigger('click')

    expect(mockSubmitHitlDecision).toHaveBeenCalledWith('approve', '', ['diagrammer'])
  })

  it('handles HITL reject action with target agents', async () => {
    mockStore.isHitlRequired = true
    const wrapper = mount(ChatPanel, {
      props: { messages: [], isDebating: true }
    })

    const rejectBtn = wrapper.find('[data-test="hitl-reject-btn"]')
    await rejectBtn.trigger('click')

    expect(mockSubmitHitlDecision).toHaveBeenCalledWith('reject', '', [])
  })

  it('handles HITL refine flow via textarea and submit button', async () => {
    mockStore.isHitlRequired = true
    const wrapper = mount(ChatPanel, {
      props: { messages: [], isDebating: true }
    })

    const textarea = wrapper.find('textarea')
    await textarea.setValue('Añade soporte para caché distribuida con Redis')

    await wrapper.find('form').trigger('submit.prevent')

    expect(mockSubmitHitlDecision).toHaveBeenCalledWith('refine', 'Añade soporte para caché distribuida con Redis', [])
  })

  it('renders interactive diagram card with view and copy buttons when message contains mermaid block', () => {
    const messages = [
      {
        role: 'assistant' as const,
        content: 'Aquí está la arquitectura:\n```mermaid\nflowchart TD\n  Client --> Gateway\n```\n¿Te parece adecuada?',
        agentName: 'Aracne'
      }
    ]

    const wrapper = mount(ChatPanel, {
      props: { messages, isDebating: false }
    })

    expect(wrapper.find('[data-test="chat-diagram-card"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="chat-diagram-copy-btn"]').text()).toBe('Copiar')
    expect(wrapper.find('[data-test="chat-diagram-view-btn"]').text()).toBe('Ver')
    expect(wrapper.text()).not.toContain('Diagrama Mermaid.js')
    expect(wrapper.text()).toContain('Aquí está la arquitectura:')
    expect(wrapper.text()).toContain('¿Te parece adecuada?')
  })

  it('copies diagram code to clipboard when clicking Copiar in chat card', async () => {
    const writeTextSpy = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, { clipboard: { writeText: writeTextSpy } })

    const messages = [
      {
        role: 'assistant' as const,
        content: '```mermaid\nflowchart TD\n  A --> B\n```',
        agentName: 'Aracne'
      }
    ]

    const wrapper = mount(ChatPanel, {
      props: { messages, isDebating: false }
    })

    const copyBtn = wrapper.find('[data-test="chat-diagram-copy-btn"]')
    expect(copyBtn.exists()).toBe(true)
    await copyBtn.trigger('click')

    expect(writeTextSpy).toHaveBeenCalledWith('flowchart TD\n  A --> B')
  })

  it('opens DiagramModal when clicking Ver diagrama button', async () => {
    const messages = [
      {
        role: 'assistant' as const,
        content: '```mermaid\nflowchart TD\n  A --> B\n```',
        agentName: 'Aracne'
      }
    ]

    const wrapper = mount(ChatPanel, {
      props: { messages, isDebating: false }
    })

    // Before click, modal backdrop does not exist
    expect(wrapper.find('[data-test="diagram-modal-backdrop"]').exists()).toBe(false)

    const viewBtn = wrapper.find('[data-test="chat-diagram-view-btn"]')
    expect(viewBtn.exists()).toBe(true)
    await viewBtn.trigger('click')

    // After click, modal is open
    expect(wrapper.find('[data-test="diagram-modal-backdrop"]').exists()).toBe(true)
  })

  it('filters out mermaid diagram syntax from TTS audio synthesis', async () => {
    mockStore.isVoiceOutputEnabled = true
    mockStore.playTtsAudioChunk = vi.fn().mockResolvedValue(undefined)
    mockStore.stopTts = vi.fn()

    const fetchCalls: Array<{ url: string; opts?: { body?: string } }> = []
    global.fetch = vi.fn().mockImplementation((url, opts) => {
      fetchCalls.push({ url: String(url), opts })
      return Promise.resolve({
        ok: true,
        arrayBuffer: () => Promise.resolve(new ArrayBuffer(8))
      })
    })

    const wrapper = mount(ChatPanel, {
      props: { messages: [], isDebating: false }
    })

    await wrapper.setProps({
      messages: [
        {
          role: 'assistant',
          content: 'He diseñado la topología:\n```mermaid\nflowchart TD\n  Frontend --> Backend\n```\nPor favor revísala.',
          agentName: 'Aracne'
        }
      ]
    })

    expect(global.fetch).toHaveBeenCalled()
    const synthCall = fetchCalls.find(call => call.url === '/api/audio/synthesize')
    expect(synthCall).toBeDefined()
    const body = JSON.parse(synthCall?.opts?.body || '{}')
    expect(body.text).not.toContain('flowchart')
    expect(body.text).not.toContain('Frontend --> Backend')
  })
})

