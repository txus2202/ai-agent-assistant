import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import InitialSetupView from '../InitialSetupView.vue'
import { useAuthStore } from '../../stores/auth'
import { useDebateStore } from '../../stores/debate'

const mockPush = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}))

describe('InitialSetupView.vue', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockPush.mockReset()
    vi.restoreAllMocks()
  })

  it('renders initial setup form properly', () => {
    const wrapper = mount(InitialSetupView)
    expect(wrapper.find('input[data-test="username"]').exists()).toBe(true)
    expect(wrapper.find('input[data-test="password"]').exists()).toBe(true)
    expect(wrapper.find('input[data-test="confirm-password"]').exists()).toBe(true)
    expect(wrapper.find('button[type="submit"]').exists()).toBe(true)
  })

  it('renders dynamic project name from debateStore', () => {
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
    const wrapper = mount(InitialSetupView)
    expect(wrapper.text()).toContain('PEPOTEZOTE')
  })

  it('validates empty fields', async () => {
    const wrapper = mount(InitialSetupView)
    await wrapper.find('form').trigger('submit.prevent')

    expect(wrapper.text()).toContain('Por favor, complete todos los campos')
    expect(mockPush).not.toHaveBeenCalled()
  })

  it('validates password length minimum 8 chars', async () => {
    const wrapper = mount(InitialSetupView)
    await wrapper.find('input[data-test="username"]').setValue('admin')
    await wrapper.find('input[data-test="password"]').setValue('short')
    await wrapper.find('input[data-test="confirm-password"]').setValue('short')
    await wrapper.find('form').trigger('submit.prevent')

    expect(wrapper.text()).toContain('La contraseña debe tener al menos 8 caracteres')
    expect(mockPush).not.toHaveBeenCalled()
  })

  it('validates matching passwords', async () => {
    const wrapper = mount(InitialSetupView)
    await wrapper.find('input[data-test="username"]').setValue('admin')
    await wrapper.find('input[data-test="password"]').setValue('password123')
    await wrapper.find('input[data-test="confirm-password"]').setValue('different123')
    await wrapper.find('form').trigger('submit.prevent')

    expect(wrapper.text()).toContain('Las contraseñas no coinciden')
    expect(mockPush).not.toHaveBeenCalled()
  })

  it('submits setup and redirects on success', async () => {
    const authStore = useAuthStore()
    vi.spyOn(authStore, 'setupInitialAdmin').mockResolvedValue(true)

    const wrapper = mount(InitialSetupView)
    await wrapper.find('input[data-test="username"]').setValue('admin')
    await wrapper.find('input[data-test="password"]').setValue('password123')
    await wrapper.find('input[data-test="confirm-password"]').setValue('password123')
    await wrapper.find('form').trigger('submit.prevent')

    expect(authStore.setupInitialAdmin).toHaveBeenCalledWith('admin', 'password123', undefined)
    expect(mockPush).toHaveBeenCalledWith('/')
  })

  it('requires setup token when setupTokenRequired is true in store', async () => {
    const authStore = useAuthStore()
    authStore.setupTokenRequired = true
    vi.spyOn(authStore, 'setupInitialAdmin').mockResolvedValue(true)

    const wrapper = mount(InitialSetupView)
    expect(wrapper.find('input[data-test="setup-token"]').exists()).toBe(true)

    await wrapper.find('input[data-test="username"]').setValue('admin')
    await wrapper.find('input[data-test="password"]').setValue('password123')
    await wrapper.find('input[data-test="confirm-password"]').setValue('password123')
    await wrapper.find('form').trigger('submit.prevent')

    expect(wrapper.text()).toContain('INITIAL_SETUP_TOKEN')
    expect(authStore.setupInitialAdmin).not.toHaveBeenCalled()

    await wrapper.find('input[data-test="setup-token"]').setValue('secret-bootstrap-token')
    await wrapper.find('form').trigger('submit.prevent')

    expect(authStore.setupInitialAdmin).toHaveBeenCalledWith(
      'admin',
      'password123',
      'secret-bootstrap-token',
    )
    expect(mockPush).toHaveBeenCalledWith('/')
  })
})

