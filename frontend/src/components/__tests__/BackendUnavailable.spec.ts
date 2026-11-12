import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import BackendUnavailable from '../BackendUnavailable.vue'
import { useDebateStore } from '../../stores/debate'
import { useAuthStore } from '../../stores/auth'

describe('BackendUnavailable.vue', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('renders project name and server offline message', () => {
    const debateStore = useDebateStore()
    debateStore.topology = {
      project_name: 'PEPOTEZOTE',
      supervisor: 'Atenea',
      interpreters: [],
      proposers: [],
      reviewers: [],
      evaluators: [],
      implementers: []
    }
    const wrapper = mount(BackendUnavailable)

    expect(wrapper.text()).toContain('PEPOTEZOTE')
    expect(wrapper.text()).toContain('Servidor Backend No Disponible')
    expect(wrapper.text()).toContain('SYS: OFFLINE')
  })

  it('displays the error message from authStore', () => {
    const authStore = useAuthStore()
    authStore.errorMessage = 'Conexión rechazada en el puerto 8000'

    const wrapper = mount(BackendUnavailable)
    expect(wrapper.text()).toContain('Conexión rechazada en el puerto 8000')
  })

  it('emits retry event when clicking the retry button', async () => {
    const wrapper = mount(BackendUnavailable)
    const button = wrapper.find('button')
    await button.trigger('click')

    expect(wrapper.emitted('retry')).toHaveLength(1)
  })

  it('disables button when isRetrying is true', () => {
    const wrapper = mount(BackendUnavailable, {
      props: {
        isRetrying: true
      }
    })
    const button = wrapper.find('button')
    expect(button.attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('Comprobando Servidor...')
  })

  it('renders default project name (AI AGENT ASSISTANT) when backend topology is null', () => {
    const debateStore = useDebateStore()
    debateStore.topology = null
    const wrapper = mount(BackendUnavailable)

    expect(wrapper.text()).toContain('AI AGENT ASSISTANT')
  })
})

