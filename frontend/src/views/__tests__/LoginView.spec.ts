import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import LoginView from '../LoginView.vue'
import { useAuthStore } from '../../stores/auth'

const mockPush = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
  useRoute: () => ({
    query: {},
  }),
}))

describe('LoginView.vue', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockPush.mockReset()
    vi.restoreAllMocks()
  })

  it('renders login form properly', () => {
    const wrapper = mount(LoginView)
    expect(wrapper.find('input[type="text"]').exists()).toBe(true)
    expect(wrapper.find('input[type="password"]').exists()).toBe(true)
    expect(wrapper.find('button[type="submit"]').exists()).toBe(true)
  })

  it('validates empty fields on submission', async () => {
    const wrapper = mount(LoginView)
    await wrapper.find('form').trigger('submit.prevent')

    expect(wrapper.text()).toContain('Por favor, introduzca usuario y contraseña')
    expect(mockPush).not.toHaveBeenCalled()
  })

  it('submits login and redirects on success', async () => {
    const authStore = useAuthStore()
    vi.spyOn(authStore, 'login').mockResolvedValue(true)

    const wrapper = mount(LoginView)
    await wrapper.find('input[type="text"]').setValue('admin')
    await wrapper.find('input[type="password"]').setValue('password123')
    await wrapper.find('form').trigger('submit.prevent')

    expect(authStore.login).toHaveBeenCalledWith('admin', 'password123')
    expect(mockPush).toHaveBeenCalledWith('/')
  })

  it('displays error message when login fails', async () => {
    const authStore = useAuthStore()
    vi.spyOn(authStore, 'login').mockImplementation(async () => {
      authStore.errorMessage = 'Credenciales inválidas'
      return false
    })

    const wrapper = mount(LoginView)
    await wrapper.find('input[type="text"]').setValue('admin')
    await wrapper.find('input[type="password"]').setValue('wrongpass')
    await wrapper.find('form').trigger('submit.prevent')

    expect(wrapper.text()).toContain('Credenciales inválidas')
    expect(mockPush).not.toHaveBeenCalled()
  })
})

