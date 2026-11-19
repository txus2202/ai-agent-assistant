import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '../auth'
import { authService } from '../../services/authService'
import { HttpError } from '../../services/httpClient'

describe('useAuthStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('initializes with default state', () => {
    const store = useAuthStore()
    expect(store.user).toBeNull()
    expect(store.isInitialized).toBeNull()
    expect(store.isBackendAvailable).toBeNull()
    expect(store.isLoading).toBe(false)
    expect(store.errorMessage).toBeNull()
    expect(store.isAuthenticated).toBe(false)
    expect(store.isAdmin).toBe(false)
  })

  it('checks auth when backend is unavailable or throws network error', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    vi.spyOn(authService, 'getStatus').mockRejectedValue(
      new Error('Network error: Connection refused'),
    )

    const store = useAuthStore()
    await store.checkAuth()

    expect(store.isBackendAvailable).toBe(false)
    expect(store.isInitialized).toBeNull()
    expect(store.user).toBeNull()
    expect(store.errorMessage).toContain('No se ha podido conectar')
  })

  it('checks auth when backend responds with 502/503 server error', async () => {
    vi.spyOn(authService, 'getStatus').mockRejectedValue(
      new HttpError('Bad Gateway', 502),
    )

    const store = useAuthStore()
    await store.checkAuth()

    expect(store.isBackendAvailable).toBe(false)
    expect(store.isInitialized).toBeNull()
    expect(store.user).toBeNull()
    expect(store.errorMessage).toContain('no está disponible')
  })

  it('checks auth when system is not initialized', async () => {
    vi.spyOn(authService, 'getStatus').mockResolvedValue({ initialized: false })

    const store = useAuthStore()
    await store.checkAuth()

    expect(store.isInitialized).toBe(false)
    expect(store.user).toBeNull()
    expect(store.isAuthenticated).toBe(false)
  })

  it('checks auth when system is initialized and user is authenticated', async () => {
    const mockUser = {
      id: 'usr-1',
      username: 'admin',
      is_admin: true,
      is_active: true,
      created_at: '2026-11-09T00:00:00',
    }
    vi.spyOn(authService, 'getStatus').mockResolvedValue({
      initialized: true,
      authenticated: true,
      user: mockUser,
    })

    const store = useAuthStore()
    await store.checkAuth()

    expect(store.isInitialized).toBe(true)
    expect(store.user).toEqual(mockUser)
    expect(store.isAuthenticated).toBe(true)
    expect(store.isAdmin).toBe(true)
  })

  it('checks auth when system is initialized but user session is expired / not logged in', async () => {
    vi.spyOn(authService, 'getStatus').mockResolvedValue({
      initialized: true,
      authenticated: false,
      user: null,
    })

    const store = useAuthStore()
    await store.checkAuth()

    expect(store.isInitialized).toBe(true)
    expect(store.user).toBeNull()
    expect(store.isAuthenticated).toBe(false)
  })

  it('handles successful login', async () => {
    const mockUser = {
      id: 'usr-1',
      username: 'architect',
      is_admin: false,
      is_active: true,
      created_at: '2026-11-09T00:00:00',
    }
    const loginSpy = vi.spyOn(authService, 'login').mockResolvedValue({
      token: 'jwt-token',
      user: mockUser,
    })

    const store = useAuthStore()
    const result = await store.login('architect', 'secret123')

    expect(loginSpy).toHaveBeenCalledWith('architect', 'secret123')
    expect(result).toBe(true)
    expect(store.user).toEqual(mockUser)
    expect(store.isAuthenticated).toBe(true)
    expect(store.isAdmin).toBe(false)
    expect(store.errorMessage).toBeNull()
  })

  it('handles failed login', async () => {
    vi.spyOn(authService, 'login').mockRejectedValue(
      new HttpError('Credenciales inválidas', 401, 'Credenciales inválidas'),
    )

    const store = useAuthStore()
    const result = await store.login('wrong', 'wrongpass')

    expect(result).toBe(false)
    expect(store.user).toBeNull()
    expect(store.isAuthenticated).toBe(false)
    expect(store.errorMessage).toBe('Credenciales inválidas')
  })

  it('handles successful initial admin setup', async () => {
    const mockAdmin = {
      id: 'usr-admin',
      username: 'root',
      is_admin: true,
      is_active: true,
      created_at: '2026-11-09T00:00:00',
    }
    const setupSpy = vi.spyOn(authService, 'setupInitialAdmin').mockResolvedValue({
      token: 'admin-jwt',
      user: mockAdmin,
    })

    const store = useAuthStore()
    const result = await store.setupInitialAdmin('root', 'strongPassword123')

    expect(setupSpy).toHaveBeenCalledWith('root', 'strongPassword123', undefined)
    expect(result).toBe(true)
    expect(store.isInitialized).toBe(true)
    expect(store.user).toEqual(mockAdmin)
    expect(store.isAuthenticated).toBe(true)
    expect(store.isAdmin).toBe(true)
  })

  it('handles logout', async () => {
    const store = useAuthStore()
    store.user = {
      id: 'usr-1',
      username: 'admin',
      is_admin: true,
      is_active: true,
      created_at: '2026-11-09T00:00:00',
    }
    store.users = [store.user]

    const logoutSpy = vi.spyOn(authService, 'logout').mockResolvedValue({
      message: 'Logged out successfully',
    })

    await store.logout()

    expect(logoutSpy).toHaveBeenCalledTimes(1)
    expect(store.user).toBeNull()
    expect(store.users).toEqual([])
    expect(store.isAuthenticated).toBe(false)
  })

  it('fetches users list successfully for admin', async () => {
    const mockUsers = [
      { id: 'usr-1', username: 'admin', is_admin: true, is_active: true, created_at: '2026-11-09T00:00:00' },
      { id: 'usr-2', username: 'operator', is_admin: false, is_active: true, created_at: '2026-11-10T00:00:00' },
    ]
    vi.spyOn(authService, 'fetchUsers').mockResolvedValue(mockUsers)

    const store = useAuthStore()
    const users = await store.fetchUsers()

    expect(users).toEqual(mockUsers)
    expect(store.users).toEqual(mockUsers)
    expect(store.usersLoading).toBe(false)
  })

  it('handles fetch users failure', async () => {
    vi.spyOn(authService, 'fetchUsers').mockRejectedValue(
      new HttpError('Acceso denegado', 403, 'Acceso denegado'),
    )

    const store = useAuthStore()
    const users = await store.fetchUsers()

    expect(users).toEqual([])
    expect(store.users).toEqual([])
    expect(store.errorMessage).toBe('Acceso denegado')
  })

  it('creates a new user successfully and appends to users list', async () => {
    const newUser = {
      id: 'usr-3',
      username: 'new_operator',
      is_admin: false,
      is_active: true,
      created_at: '2026-11-10T12:00:00',
    }
    const createSpy = vi.spyOn(authService, 'createUser').mockResolvedValue(newUser)

    const store = useAuthStore()
    const created = await store.createUser('new_operator', 'securePass123', false)

    expect(createSpy).toHaveBeenCalledWith({
      username: 'new_operator',
      password: 'securePass123',
      is_admin: false,
    })
    expect(created).toEqual(newUser)
    expect(store.users).toContainEqual(newUser)
    expect(store.errorMessage).toBeNull()
  })

  it('handles create user error (e.g. user already exists)', async () => {
    vi.spyOn(authService, 'createUser').mockRejectedValue(
      new HttpError('User already exists', 409, 'User already exists'),
    )

    const store = useAuthStore()
    const created = await store.createUser('existing_user', 'securePass123')

    expect(created).toBeNull()
    expect(store.errorMessage).toBe('User already exists')
  })

  it('updates a user successfully and updates store state', async () => {
    const store = useAuthStore()
    const originalUser = { id: 'usr-1', username: 'bob', is_admin: false, is_active: true, created_at: '2026-11-10T12:00:00' }
    const updatedUser = { id: 'usr-1', username: 'bob', is_admin: true, is_active: false, created_at: '2026-11-10T12:00:00' }
    store.users = [originalUser]

    const updateSpy = vi.spyOn(authService, 'updateUser').mockResolvedValue(updatedUser)

    const res = await store.updateUser('usr-1', { is_admin: true, is_active: false })

    expect(updateSpy).toHaveBeenCalledWith('usr-1', { is_admin: true, is_active: false })
    expect(res).toEqual(updatedUser)
    expect(store.users[0]).toEqual(updatedUser)
  })

  it('handles deleteUser with soft delete strategy', async () => {
    const store = useAuthStore()
    const user = { id: 'usr-2', username: 'charlie', is_admin: false, is_active: true, created_at: '2026-11-10T12:00:00' }
    store.users = [user]

    const delSpy = vi.spyOn(authService, 'deleteUser').mockResolvedValue({
      message: 'User successfully deactivated (soft delete)',
      strategy: 'soft',
    })

    const result = await store.deleteUser('usr-2')

    expect(delSpy).toHaveBeenCalledWith('usr-2')
    expect(result.success).toBe(true)
    expect(result.strategy).toBe('soft')
    expect(store.users[0]?.is_active).toBe(false)
  })

  it('handles deleteUser with hard delete strategy', async () => {
    const store = useAuthStore()
    const user = { id: 'usr-3', username: 'dave', is_admin: false, is_active: true, created_at: '2026-11-10T12:00:00' }
    store.users = [user]

    vi.spyOn(authService, 'deleteUser').mockResolvedValue({
      message: 'User permanently deleted (hard delete)',
      strategy: 'hard',
    })

    const result = await store.deleteUser('usr-3')

    expect(result.success).toBe(true)
    expect(result.strategy).toBe('hard')
    expect(store.users).toEqual([])
  })
})
