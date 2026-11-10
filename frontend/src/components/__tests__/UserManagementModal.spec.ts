import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import UserManagementModal from '../UserManagementModal.vue'
import { useAuthStore } from '../../stores/auth'

// Mock @lucide/vue icons
vi.mock('@lucide/vue', () => ({
  X: { template: '<svg data-test="close-icon"></svg>' },
  Users: { template: '<svg data-test="users-icon"></svg>' },
  UserPlus: { template: '<svg data-test="user-plus-icon"></svg>' },
  Shield: { template: '<svg data-test="shield-icon"></svg>' },
  ShieldCheck: { template: '<svg data-test="shield-check-icon"></svg>' },
  KeyRound: { template: '<svg data-test="key-icon"></svg>' },
  RefreshCw: { template: '<svg data-test="refresh-icon"></svg>' },
  CheckCircle2: { template: '<svg data-test="check-icon"></svg>' },
  AlertCircle: { template: '<svg data-test="alert-icon"></svg>' },
  Edit2: { template: '<svg data-test="edit-icon"></svg>' },
  Trash2: { template: '<svg data-test="trash-icon"></svg>' },
  Power: { template: '<svg data-test="power-icon"></svg>' },
}))

describe('UserManagementModal.vue', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('does not render when isOpen is false', () => {
    const wrapper = mount(UserManagementModal, {
      props: {
        isOpen: false,
        teleportDisabled: true,
      },
    })
    expect(wrapper.find('dialog').exists()).toBe(false)
  })

  it('renders modal and fetches users when isOpen is true', async () => {
    const authStore = useAuthStore()
    const fetchSpy = vi.spyOn(authStore, 'fetchUsers').mockResolvedValue([])

    const wrapper = mount(UserManagementModal, {
      props: {
        isOpen: true,
        teleportDisabled: true,
      },
    })

    expect(wrapper.find('dialog').exists()).toBe(true)
    expect(wrapper.text().toUpperCase()).toContain('GESTIÓN DE OPERADORES')
    expect(fetchSpy).toHaveBeenCalledTimes(1)
  })

  it('renders list of existing users with their role badges', async () => {
    const authStore = useAuthStore()
    authStore.users = [
      {
        id: 'usr-1',
        username: 'master_admin',
        is_admin: true,
        is_active: true,
        created_at: '2026-11-09T00:00:00Z',
      },
      {
        id: 'usr-2',
        username: 'operator_alpha',
        is_admin: false,
        is_active: true,
        created_at: '2026-11-10T00:00:00Z',
      },
    ]
    vi.spyOn(authStore, 'fetchUsers').mockResolvedValue(authStore.users)

    const wrapper = mount(UserManagementModal, {
      props: {
        isOpen: true,
        teleportDisabled: true,
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('master_admin')
    expect(wrapper.text()).toContain('operator_alpha')
    expect(wrapper.text()).toContain('ADMINISTRADOR')
    expect(wrapper.text()).toContain('OPERADOR')
  })

  it('emits close when clicking the close button or backdrop', async () => {
    const wrapper = mount(UserManagementModal, {
      props: {
        isOpen: true,
        teleportDisabled: true,
      },
    })

    const closeBtn = wrapper.find('[data-test="close-modal-btn"]')
    expect(closeBtn.exists()).toBe(true)
    await closeBtn.trigger('click')

    expect(wrapper.emitted('close')).toBeTruthy()
  })

  it('validates password mismatch before calling createUser', async () => {
    const authStore = useAuthStore()
    const createSpy = vi.spyOn(authStore, 'createUser').mockResolvedValue(null)

    const wrapper = mount(UserManagementModal, {
      props: {
        isOpen: true,
        teleportDisabled: true,
      },
    })

    await wrapper.find('[data-test="username-input"]').setValue('newuser')
    await wrapper.find('[data-test="password-input"]').setValue('password123')
    await wrapper.find('[data-test="confirm-password-input"]').setValue('differentPass123')
    await wrapper.find('form').trigger('submit.prevent')

    expect(wrapper.text()).toContain('Las contraseñas no coinciden')
    expect(createSpy).not.toHaveBeenCalled()
  })

  it('validates minimum password length', async () => {
    const authStore = useAuthStore()
    const createSpy = vi.spyOn(authStore, 'createUser').mockResolvedValue(null)

    const wrapper = mount(UserManagementModal, {
      props: {
        isOpen: true,
        teleportDisabled: true,
      },
    })

    await wrapper.find('[data-test="username-input"]').setValue('newuser')
    await wrapper.find('[data-test="password-input"]').setValue('short')
    await wrapper.find('[data-test="confirm-password-input"]').setValue('short')
    await wrapper.find('form').trigger('submit.prevent')

    expect(wrapper.text()).toContain('al menos 8 caracteres')
    expect(createSpy).not.toHaveBeenCalled()
  })

  it('creates user successfully and resets the form', async () => {
    const authStore = useAuthStore()
    const mockCreatedUser = {
      id: 'usr-new',
      username: 'agent_smith',
      is_admin: true,
      is_active: true,
      created_at: '2026-11-10T12:00:00Z',
    }
    const createSpy = vi.spyOn(authStore, 'createUser').mockResolvedValue(mockCreatedUser)

    const wrapper = mount(UserManagementModal, {
      props: {
        isOpen: true,
        teleportDisabled: true,
      },
    })

    await wrapper.find('[data-test="username-input"]').setValue('agent_smith')
    await wrapper.find('[data-test="password-input"]').setValue('matrixSecure123')
    await wrapper.find('[data-test="confirm-password-input"]').setValue('matrixSecure123')
    await wrapper.find('[data-test="is-admin-checkbox"]').setValue(true)
    await wrapper.find('form').trigger('submit.prevent')

    await flushPromises()

    expect(createSpy).toHaveBeenCalledWith('agent_smith', 'matrixSecure123', true)
    expect(wrapper.text()).toContain('Operador creado correctamente')

    const usernameInput = wrapper.find('[data-test="username-input"]').element as HTMLInputElement
    expect(usernameInput.value).toBe('')
  })

  it('toggles user active status when clicking toggle button', async () => {
    const authStore = useAuthStore()
    authStore.user = { id: 'admin-1', username: 'admin', is_admin: true, is_active: true, created_at: '' }
    const targetUser = { id: 'usr-2', username: 'bob', is_admin: false, is_active: true, created_at: '' }
    authStore.users = [authStore.user, targetUser]
    vi.spyOn(authStore, 'fetchUsers').mockResolvedValue(authStore.users)
    const updateSpy = vi.spyOn(authStore, 'updateUser').mockResolvedValue({ ...targetUser, is_active: false })

    const wrapper = mount(UserManagementModal, {
      props: {
        isOpen: true,
        teleportDisabled: true,
      },
    })
    await flushPromises()

    const toggleBtns = wrapper.findAll('[data-test="toggle-active-btn"]')
    expect(toggleBtns.length).toBe(2)

    // Second button belongs to targetUser
    await toggleBtns[1]?.trigger('click')

    expect(updateSpy).toHaveBeenCalledWith('usr-2', { is_active: false })
  })

  it('disables self-deactivation and self-deletion for current logged-in user', async () => {
    const authStore = useAuthStore()
    authStore.user = { id: 'admin-1', username: 'admin', is_admin: true, is_active: true, created_at: '' }
    authStore.users = [authStore.user]
    vi.spyOn(authStore, 'fetchUsers').mockResolvedValue(authStore.users)

    const wrapper = mount(UserManagementModal, {
      props: {
        isOpen: true,
        teleportDisabled: true,
      },
    })
    await flushPromises()

    const toggleBtn = wrapper.find('[data-test="toggle-active-btn"]')
    expect((toggleBtn.element as HTMLButtonElement).disabled).toBe(true)

    const deleteBtn = wrapper.find('[data-test="delete-user-btn"]')
    expect((deleteBtn.element as HTMLButtonElement).disabled).toBe(true)
  })

  it('opens edit form, updates role and password, and saves', async () => {
    const authStore = useAuthStore()
    authStore.user = { id: 'admin-1', username: 'admin', is_admin: true, is_active: true, created_at: '' }
    const targetUser = { id: 'usr-2', username: 'bob', is_admin: false, is_active: true, created_at: '' }
    authStore.users = [authStore.user, targetUser]
    vi.spyOn(authStore, 'fetchUsers').mockResolvedValue(authStore.users)
    const updateSpy = vi.spyOn(authStore, 'updateUser').mockResolvedValue({ ...targetUser, is_admin: true })

    const wrapper = mount(UserManagementModal, {
      props: {
        isOpen: true,
        teleportDisabled: true,
      },
    })
    await flushPromises()

    const editBtns = wrapper.findAll('[data-test="edit-user-btn"]')
    await editBtns[1]?.trigger('click') // Open edit form for bob

    expect(wrapper.find('[data-test="edit-user-form"]').exists()).toBe(true)

    await wrapper.find('[data-test="edit-is-admin-checkbox"]').setValue(true)
    await wrapper.find('[data-test="edit-password-input"]').setValue('BrandNewPassword123!')
    await wrapper.find('[data-test="save-edit-btn"]').trigger('click')

    expect(updateSpy).toHaveBeenCalledWith('usr-2', {
      is_admin: true,
      password: 'BrandNewPassword123!',
    })
  })

  it('confirms and deletes user', async () => {
    const authStore = useAuthStore()
    authStore.user = { id: 'admin-1', username: 'admin', is_admin: true, is_active: true, created_at: '' }
    const targetUser = { id: 'usr-2', username: 'bob', is_admin: false, is_active: true, created_at: '' }
    authStore.users = [authStore.user, targetUser]
    vi.spyOn(authStore, 'fetchUsers').mockResolvedValue(authStore.users)
    const deleteSpy = vi.spyOn(authStore, 'deleteUser').mockResolvedValue({ success: true, strategy: 'soft' })

    const wrapper = mount(UserManagementModal, {
      props: {
        isOpen: true,
        teleportDisabled: true,
      },
    })
    await flushPromises()

    const deleteBtns = wrapper.findAll('[data-test="delete-user-btn"]')
    await deleteBtns[1]?.trigger('click') // Prompt confirm for bob

    expect(wrapper.find('[data-test="confirm-delete-box"]').exists()).toBe(true)

    await wrapper.find('[data-test="confirm-delete-btn"]').trigger('click')

    expect(deleteSpy).toHaveBeenCalledWith('usr-2')
  })
})

