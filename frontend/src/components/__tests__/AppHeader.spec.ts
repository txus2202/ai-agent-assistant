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
  }),
  useRoute: () => ({
    path: '/'
  })
}))

// Mock @lucide/vue components
vi.mock('@lucide/vue', () => ({
  Cpu: { template: '<svg data-test="cpu-icon"></svg>' },
  Volume2: { template: '<svg data-test="volume-on"></svg>' },
  VolumeX: { template: '<svg data-test="volume-off"></svg>' },
  History: { template: '<svg data-test="history-icon"></svg>' },
  Network: { template: '<svg data-test="network-icon"></svg>' },
  Ear: { template: '<svg data-test="ear-on"></svg>' },
  EarOff: { template: '<svg data-test="ear-off"></svg>' },
  Sun: { template: '<svg data-test="sun-icon"></svg>' },
  Moon: { template: '<svg data-test="moon-icon"></svg>' },
  User: { template: '<svg data-test="user-icon"></svg>' },
  Users: { template: '<svg data-test="users-icon"></svg>' },
  LogOut: { template: '<svg data-test="logout-icon"></svg>' },
  KeyRound: { template: '<svg data-test="key-icon"></svg>' },
  X: { template: '<svg data-test="close-icon"></svg>' },
  ChevronDown: { template: '<svg data-test="chevron-down-icon"></svg>' },
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

  it('renders correctly without supervisor info or SYSTEM CORE and displays the Atenea owl icon', () => {
    const store = useDebateStore()
    const wrapper = mount(AppHeader)
    expect(wrapper.text().toUpperCase()).not.toContain('SYSTEM CORE')
    expect(wrapper.text()).toContain(store.projectName)
    expect(wrapper.text()).not.toContain('SUPERVISOR:')
    const brandIcon = wrapper.find('[data-test="atenea-brand-icon"]')
    expect(brandIcon.exists()).toBe(true)
    expect(brandIcon.attributes('src')).toBe('/atenea-icon.png')
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

  it('renders topology button immediately to the right of history button and navigates to /topology', async () => {
    const wrapper = mount(AppHeader)
    const rightButtons = wrapper.find('[data-test="header-right-section"]').findAll('button')
    const historyIdx = rightButtons.findIndex((b) => b.attributes('data-test') === 'history-btn')
    const topologyIdx = rightButtons.findIndex((b) => b.attributes('data-test') === 'topology-btn')

    expect(historyIdx).toBeGreaterThanOrEqual(0)
    expect(topologyIdx).toBe(historyIdx + 1)

    await rightButtons[topologyIdx]!.trigger('click')
    expect(pushMock).toHaveBeenCalledWith('/topology')
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

  it('applies active styling to speaker button when voice output is enabled', () => {
    const wrapper = mount(AppHeader)
    const store = useDebateStore()
    store.isVoiceOutputEnabled = true
    const audioButton = wrapper.find('button[title="Toggle System Audio"]')
    expect(audioButton.classes()).toContain('border-cyan-400')
    expect(audioButton.classes()).toContain('bg-space-800')
    expect(audioButton.classes()).toContain('text-cyan-200')
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

  it('shares matching cyan hover and active color schemes between speaker, auto-listen, and history buttons matching operator menu', async () => {
    const wrapper = mount(AppHeader)
    const store = useDebateStore()
    store.isVoiceOutputEnabled = true
    store.isAutoListenEnabled = true
    await wrapper.vm.$nextTick()

    const speakerBtn = wrapper.find('button[title="Toggle System Audio"]')
    const autoListenBtn = wrapper.find('button[title="Toggle Auto-Listen (Wake Word)"]')
    const historyBtn = wrapper.find('button[title="Debate History"]')

    // Both active buttons share cyan active border and background matching user menu button
    expect(speakerBtn.classes()).toContain('border-cyan-400')
    expect(speakerBtn.classes()).toContain('bg-space-800')
    expect(autoListenBtn.classes()).toContain('border-cyan-400')
    expect(autoListenBtn.classes()).toContain('bg-space-800')

    // History button shares the same operator-style cyan border and hover styling
    expect(historyBtn.classes()).toContain('border-cyan-800/40')
    expect(historyBtn.classes()).toContain('hover:text-cyan-200')
    expect(historyBtn.classes()).toContain('hover:border-cyan-500/50')
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

    // Open user menu to access logout
    const menuBtn = wrapper.find('[data-test="user-menu-btn"]')
    expect(menuBtn.exists()).toBe(true)
    await menuBtn.trigger('click')

    const logoutBtn = wrapper.find('[data-test="logout-btn"]')
    expect(logoutBtn.exists()).toBe(true)

    const logoutSpy = vi.spyOn(authStore, 'logout').mockResolvedValue(undefined)
    await logoutBtn.trigger('click')

    expect(logoutSpy).toHaveBeenCalled()
    expect(pushMock).toHaveBeenCalledWith('/login')
  })

  it('hides user management button for regular non-admin users inside dropdown', async () => {
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
    await wrapper.find('[data-test="user-menu-btn"]').trigger('click')
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
    await wrapper.find('[data-test="user-menu-btn"]').trigger('click')

    const manageBtn = wrapper.find('[data-test="manage-users-btn"]')
    expect(manageBtn.exists()).toBe(true)

    // Modal initially closed
    expect(wrapper.find('[data-test="user-management-modal-stub"]').exists()).toBe(false)

    // Click to open modal
    await manageBtn.trigger('click')
    expect(wrapper.find('[data-test="user-management-modal-stub"]').exists()).toBe(true)
  })

  it('allows regular authenticated users to open self-service change password modal via dropdown', async () => {
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
    await wrapper.find('[data-test="user-menu-btn"]').trigger('click')

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

  it('toggles user menu dropdown and closes when clicking outside', async () => {
    const { useAuthStore } = await import('../../stores/auth')
    const authStore = useAuthStore()
    authStore.user = {
      id: 'usr-1',
      username: 'architect',
      is_admin: false,
      is_active: true,
      created_at: '2026-11-09T00:00:00',
    }

    const wrapper = mount(AppHeader, { attachTo: document.body })
    const menuBtn = wrapper.find('[data-test="user-menu-btn"]')

    expect(wrapper.find('[data-test="user-menu-dropdown"]').exists()).toBe(false)

    // Open
    await menuBtn.trigger('click')
    expect(wrapper.find('[data-test="user-menu-dropdown"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('OPERADOR')

    // Close on toggle
    await menuBtn.trigger('click')
    expect(wrapper.find('[data-test="user-menu-dropdown"]').exists()).toBe(false)

    // Reopen and click outside
    await menuBtn.trigger('click')
    expect(wrapper.find('[data-test="user-menu-dropdown"]').exists()).toBe(true)

    document.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-test="user-menu-dropdown"]').exists()).toBe(false)

    wrapper.unmount()
  })

  it('displays only the first word of the username up to the first space in the button badge', async () => {
    const { useAuthStore } = await import('../../stores/auth')
    const authStore = useAuthStore()
    authStore.user = {
      id: 'usr-multi',
      username: 'Juan Antonio',
      is_admin: false,
      is_active: true,
      created_at: '2026-11-09T00:00:00',
    }

    const wrapper = mount(AppHeader)
    const userBadge = wrapper.find('[data-test="user-badge"]')
    expect(userBadge.text()).toBe('Juan')
    expect(userBadge.text()).not.toContain('Antonio')
  })

  it('aligns operator account dropdown and theme switcher to the left with 16px padding and 16px gap across all viewports', () => {
    const wrapper = mount(AppHeader)
    
    // Left section is aligned to the left with 16px padding (pl-4) and 16px gap (gap-4)
    const leftSection = wrapper.find('[data-test="header-left-section"]')
    expect(leftSection.classes()).toContain('flex')
    expect(leftSection.classes()).toContain('items-center')
    expect(leftSection.classes()).toContain('justify-start')
    expect(leftSection.classes()).toContain('pl-4')
    expect(leftSection.classes()).toContain('gap-4')
    expect(leftSection.classes()).toContain('xl:w-[380px]')
    expect(leftSection.classes()).toContain('2xl:w-[400px]')

    // Right section has right padding and action controls with 16px gap (gap-4)
    const rightSection = wrapper.find('[data-test="header-right-section"]')
    expect(rightSection.classes()).toContain('flex')
    expect(rightSection.classes()).toContain('justify-end')
    expect(rightSection.classes()).toContain('pr-4')
    expect(rightSection.classes()).toContain('gap-4')

    // Center banner is present in mobile, centered at the top (order-1), and centered on sm+ (sm:order-2)
    const centerBanner = wrapper.find('[data-test="header-center-banner"]')
    expect(centerBanner.classes()).toContain('flex')
    expect(centerBanner.classes()).toContain('justify-center')
    expect(centerBanner.classes()).toContain('order-1')
    expect(centerBanner.classes()).toContain('sm:order-2')
    const store = useDebateStore()
    expect(centerBanner.text()).toContain(store.projectName)
  })
})
