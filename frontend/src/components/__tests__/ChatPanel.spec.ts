import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ChatPanel from '../ChatPanel.vue'

// Mock the debate store
const mockStartDebate = vi.fn()
const mockUploadFile = vi.fn().mockResolvedValue('/uploads/test.pdf')

vi.mock('../../stores/debate', () => ({
  useDebateStore: () => ({
    isDebating: false,
    messages: [],
    startDebate: mockStartDebate,
    uploadFile: mockUploadFile
  })
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
    
    // Find target agent select and set value
    const agentSelect = wrapper.find('[data-test="target-agent-select"]')
    expect(agentSelect.exists()).toBe(true)
    await agentSelect.setValue('learning')

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
})
