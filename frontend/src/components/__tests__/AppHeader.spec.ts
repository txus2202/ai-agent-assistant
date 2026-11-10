import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import AppHeader from '../AppHeader.vue'
import { useDebateStore } from '../../stores/debate'

// Mock vue-router
const pushMock = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: pushMock
  })
}))

// Mock @lucide/vue components
vi.mock('@lucide/vue', () => ({
  Cpu: { template: '<svg data-test="cpu-icon"></svg>' },
  Volume2: { template: '<svg data-test="volume-on"></svg>' },
  VolumeX: { template: '<svg data-test="volume-off"></svg>' },
  History: { template: '<svg data-test="history-icon"></svg>' },
  Ear: { template: '<svg data-test="ear-on"></svg>' },
  EarOff: { template: '<svg data-test="ear-off"></svg>' },
  Sun: { template: '<svg data-test="sun-icon"></svg>' },
  Moon: { template: '<svg data-test="moon-icon"></svg>' },
  User: { template: '<svg data-test="user-icon"></svg>' },
  Users: { template: '<svg data-test="users-icon"></svg>' },
  LogOut: { template: '<svg data-test="logout-icon"></svg>' },
  KeyRound: { template: '<svg data-test="key-icon"></svg>' },
  X: { template: '<svg data-test="close-icon"></svg>' },
}))

// Mock UserManagementModal to keep AppHeader tests isolated
vi.mock('../UserManagementModal.vue', () => ({
  default: {
    name: 'UserManagementModal',
    props: ['isOpen'],
    emits: ['close'],
    template: '<div v-if="isOpen" data-test="user-management-modal-stub"></div>',
  },
}))

describe('AppHeader.vue', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(async () => {
    await flushPromises()
    vi.restoreAllMocks()
  })

  it('renders correctly with version and without supervisor info', () => {
    const wrapper = mount(AppHeader)
    expect(wrapper.text().toUpperCase()).toContain('SYSTEM CORE V')
    expect(wrapper.text()).toContain('A.T.E.N.E.A.')
    expect(wrapper.text()).not.toContain('SUPERVISOR:')
  })

  it('renders dynamic project_name and project_description from debate store topology', async () => {
    const store = useDebateStore()
    store.topology = {
      project_name: 'TITAN-CORE',
      project_description: 'Plataforma de Inteligencia Artificial Distribuida',
      supervisor: 'Atenea',
      interpreters: [],
      proposers: [],
      reviewers: [],
      evaluators: [],
      implementers: []
    }

    const wrapper = mount(AppHeader)
    expect(wrapper.text()).toContain('TITAN-CORE')
    expect(wrapper.text()).toContain('Plataforma de Inteligencia Artificial Distribuida')
  })

  it('renders theme toggle button on the right and toggles dark/light mode', async () => {
    const wrapper = mount(AppHeader)
    const toggleBtn = wrapper.find('[data-test="theme-toggle-btn"]')
    expect(toggleBtn.exists()).toBe(true)
    
    // Initial state is dark mode (shows moon)
    expect(wrapper.find('[data-test="moon-icon"]').exists()).toBe(true)

    // Click to toggle to light mode
    await toggleBtn.trigger('click')
    expect(wrapper.find('[data-test="sun-icon"]').exists()).toBe(true)

    // Click again to toggle back to dark mode
    await toggleBtn.trigger('click')
    expect(wrapper.find('[data-test="moon-icon"]').exists()).toBe(true)
  })

  it('navigates to history on button click', async () => {
    const wrapper = mount(AppHeader)
    const historyButton = wrapper.find('button[title="Debate History"]')
    await historyButton.trigger('click')
    expect(pushMock).toHaveBeenCalledWith('/history')
  })

  it('toggles audio on button click', async () => {
    const wrapper = mount(AppHeader)
    const store = useDebateStore()
    const audioButton = wrapper.find('button[title="Toggle System Audio"]')
    
    // Initial state: Voice output is enabled by default
    expect(store.isVoiceOutputEnabled).toBe(true)
    
    await audioButton.trigger('click')
    
    // After click: Voice output should be disabled
    expect(store.isVoiceOutputEnabled).toBe(false)
  })

  it('applies desktop active styling to speaker button when voice output is enabled', () => {
    const wrapper = mount(AppHeader)
    const store = useDebateStore()
    store.isVoiceOutputEnabled = true
    const audioButton = wrapper.find('button[title="Toggle System Audio"]')
    expect(audioButton.classes()).toContain('xl:text-amber-400')
    expect(audioButton.classes()).toContain('xl:bg-amber-900/30')
  })

  it('toggles auto-listen on button click', async () => {
    const wrapper = mount(AppHeader)
    const store = useDebateStore()
    const autoListenButton = wrapper.find('button[title="Toggle Auto-Listen (Wake Word)"]')
    
    expect(store.isAutoListenEnabled).toBe(false)
    
    // In our component, we mock startAutoListen to avoid WebSocket connections
    store.startAutoListen = vi.fn().mockImplementation(() => { store.isAutoListenEnabled = true })
    store.stopAutoListen = vi.fn().mockImplementation(() => { store.isAutoListenEnabled = false })
    
    await autoListenButton.trigger('click')
    
    expect(store.startAutoListen).toHaveBeenCalled()
    expect(store.isAutoListenEnabled).toBe(true)
    
    await autoListenButton.trigger('click')
    expect(store.stopAutoListen).toHaveBeenCalled()
    expect(store.isAutoListenEnabled).toBe(false)
  })

  it('shares matching amber hover and active color schemes between speaker, auto-listen, and history buttons', async () => {
    const wrapper = mount(AppHeader)
    const store = useDebateStore()
    store.isVoiceOutputEnabled = true
    store.isAutoListenEnabled = true
    await wrapper.vm.$nextTick()

    const speakerBtn = wrapper.find('button[title="Toggle System Audio"]')
    const autoListenBtn = wrapper.find('button[title="Toggle Auto-Listen (Wake Word)"]')
    const historyBtn = wrapper.find('button[title="Debate History"]')

    // Both active buttons share amber active background and text
    expect(speakerBtn.classes()).toContain('text-amber-600')
    expect(speakerBtn.classes()).toContain('bg-amber-500/15')
    expect(autoListenBtn.classes()).toContain('text-amber-600')
    expect(autoListenBtn.classes()).toContain('bg-amber-500/15')

    // History button shares the same hover amber styling
    expect(historyBtn.classes()).toContain('hover:text-amber-600')
    expect(historyBtn.classes()).toContain('hover:border-amber-500/40')
  })

  it('renders user badge and handles logout when authenticated', async () => {
    const { useAuthStore } = await import('../../stores/auth')
    const authStore = useAuthStore()
    authStore.user = {
      id: 'usr-1',
      username: 'architect',
      is_admin: false,
      is_active: true,
      created_at: '2026-11-09T00:00:00',
    }

    const wrapper = mount(AppHeader)
    const userBadge = wrapper.find('[data-test="user-badge"]')
    expect(userBadge.exists()).toBe(true)
    expect(userBadge.text()).toContain('architect')

    const logoutBtn = wrapper.find('[data-test="logout-btn"]')
    expect(logoutBtn.exists()).toBe(true)

    const logoutSpy = vi.spyOn(authStore, 'logout').mockResolvedValue(undefined)
    await logoutBtn.trigger('click')

    expect(logoutSpy).toHaveBeenCalled()
    expect(pushMock).toHaveBeenCalledWith('/login')
  })

  it('hides user management button for regular non-admin users', async () => {
    const { useAuthStore } = await import('../../stores/auth')
    const authStore = useAuthStore()
    authStore.user = {
      id: 'usr-1',
      username: 'architect',
      is_admin: false,
      is_active: true,
      created_at: '2026-11-09T00:00:00',
    }

    const wrapper = mount(AppHeader)
    expect(wrapper.find('[data-test="manage-users-btn"]').exists()).toBe(false)
  })

  it('shows user management button for admin users and toggles modal', async () => {
    const { useAuthStore } = await import('../../stores/auth')
    const authStore = useAuthStore()
    authStore.user = {
      id: 'usr-admin',
      username: 'sysadmin',
      is_admin: true,
      is_active: true,
      created_at: '2026-11-09T00:00:00',
    }

    const wrapper = mount(AppHeader)
    const manageBtn = wrapper.find('[data-test="manage-users-btn"]')
    expect(manageBtn.exists()).toBe(true)

    // Modal initially closed
    expect(wrapper.find('[data-test="user-management-modal-stub"]').exists()).toBe(false)

    // Click to open modal
    await manageBtn.trigger('click')
    expect(wrapper.find('[data-test="user-management-modal-stub"]').exists()).toBe(true)
  })

  it('allows regular authenticated users to open self-service change password modal', async () => {
    const { useAuthStore } = await import('../../stores/auth')
    const authStore = useAuthStore()
    authStore.user = {
      id: 'usr-1',
      username: 'architect',
      is_admin: false,
      is_active: true,
      created_at: '2026-11-09T00:00:00',
    }
    vi.spyOn(authStore, 'changePassword').mockResolvedValue(true)

    const wrapper = mount(AppHeader)
    const changePwdBtn = wrapper.find('[data-test="change-password-btn"]')
    expect(changePwdBtn.exists()).toBe(true)

    await changePwdBtn.trigger('click')
    expect(wrapper.find('[data-test="change-password-modal"]').exists()).toBe(true)

    await wrapper.find('[data-test="current-password-input"]').setValue('OldPass123!')
    await wrapper.find('[data-test="new-password-input"]').setValue('NewPass123!')
    await wrapper.find('[data-test="confirm-new-password-input"]').setValue('NewPass123!')
    await wrapper.find('[data-test="change-password-modal"] form').trigger('submit.prevent')

    expect(authStore.changePassword).toHaveBeenCalledWith('OldPass123!', 'NewPass123!')
    expect(wrapper.find('[data-test="change-password-success"]').exists()).toBe(true)
  })
})
