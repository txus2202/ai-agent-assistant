import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '../auth'

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
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error: Connection refused'))

    const store = useAuthStore()
    await store.checkAuth()

    expect(store.isBackendAvailable).toBe(false)
    expect(store.isInitialized).toBeNull()
    expect(store.user).toBeNull()
    expect(store.errorMessage).toContain('No se ha podido conectar')
  })

  it('checks auth when backend responds with 502/503 server error', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 502,
      json: () => Promise.resolve({ error: 'Bad Gateway' }),
    })

    const store = useAuthStore()
    await store.checkAuth()

    expect(store.isBackendAvailable).toBe(false)
    expect(store.isInitialized).toBeNull()
    expect(store.user).toBeNull()
    expect(store.errorMessage).toContain('no está disponible')
  })

  it('checks auth when system is not initialized', async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === '/api/auth/status') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ initialized: false })
        })
      }
      return Promise.reject(new Error('Unexpected fetch url'))
    })

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
      created_at: '2026-11-09T00:00:00'
    }

    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === '/api/auth/status') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ initialized: true, authenticated: true, user: mockUser })
        })
      }
      return Promise.reject(new Error('Unexpected fetch url'))
    })

    const store = useAuthStore()
    await store.checkAuth()

    expect(store.isInitialized).toBe(true)
    expect(store.user).toEqual(mockUser)
    expect(store.isAuthenticated).toBe(true)
    expect(store.isAdmin).toBe(true)
  })

  it('checks auth when system is initialized but user session is expired / not logged in', async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === '/api/auth/status') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ initialized: true, authenticated: false, user: null })
        })
      }
      return Promise.reject(new Error('Unexpected fetch url'))
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
      created_at: '2026-11-09T00:00:00'
    }

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ token: 'jwt-token', user: mockUser })
    })

    const store = useAuthStore()
    const result = await store.login('architect', 'secret123')

    expect(result).toBe(true)
    expect(store.user).toEqual(mockUser)
    expect(store.isAuthenticated).toBe(true)
    expect(store.isAdmin).toBe(false)
    expect(store.errorMessage).toBeNull()
  })

  it('handles failed login', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: () => Promise.resolve({ detail: 'Credenciales inválidas' })
    })

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
      created_at: '2026-11-09T00:00:00'
    }

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ token: 'admin-jwt', user: mockAdmin })
    })

    const store = useAuthStore()
    const result = await store.setupInitialAdmin('root', 'strongPassword123')

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
      created_at: '2026-11-09T00:00:00'
    }
    store.users = [store.user]

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ message: 'Logged out successfully' })
    })

    await store.logout()

    expect(store.user).toBeNull()
    expect(store.users).toEqual([])
    expect(store.isAuthenticated).toBe(false)
  })

  it('fetches users list successfully for admin', async () => {
    const mockUsers = [
      { id: 'usr-1', username: 'admin', is_admin: true, is_active: true, created_at: '2026-11-09T00:00:00' },
      { id: 'usr-2', username: 'operator', is_admin: false, is_active: true, created_at: '2026-11-10T00:00:00' }
    ]

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockUsers)
    })

    const store = useAuthStore()
    const users = await store.fetchUsers()

    expect(users).toEqual(mockUsers)
    expect(store.users).toEqual(mockUsers)
    expect(store.usersLoading).toBe(false)
  })

  it('handles fetch users failure', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: () => Promise.resolve({ detail: 'Acceso denegado' })
    })

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
      created_at: '2026-11-10T12:00:00'
    }

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(newUser)
    })

    const store = useAuthStore()
    const created = await store.createUser('new_operator', 'securePass123', false)

    expect(created).toEqual(newUser)
    expect(store.users).toContainEqual(newUser)
    expect(store.errorMessage).toBeNull()
  })

  it('handles create user error (e.g. user already exists)', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      json: () => Promise.resolve({ detail: 'User already exists' })
    })

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

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(updatedUser),
    })

    const res = await store.updateUser('usr-1', { is_admin: true, is_active: false })

    expect(res).toEqual(updatedUser)
    expect(store.users[0]).toEqual(updatedUser)
  })

  it('handles deleteUser with soft delete strategy', async () => {
    const store = useAuthStore()
    const user = { id: 'usr-2', username: 'charlie', is_admin: false, is_active: true, created_at: '2026-11-10T12:00:00' }
    store.users = [user]

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ message: 'User successfully deactivated (soft delete)', strategy: 'soft' }),
    })

    const result = await store.deleteUser('usr-2')

    expect(result.success).toBe(true)
    expect(result.strategy).toBe('soft')
    expect(store.users[0]?.is_active).toBe(false)
  })

  it('handles deleteUser with hard delete strategy', async () => {
    const store = useAuthStore()
    const user = { id: 'usr-3', username: 'dave', is_admin: false, is_active: true, created_at: '2026-11-10T12:00:00' }
    store.users = [user]

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ message: 'User permanently deleted (hard delete)', strategy: 'hard' }),
    })

    const result = await store.deleteUser('usr-3')

    expect(result.success).toBe(true)
    expect(result.strategy).toBe('hard')
    expect(store.users).toEqual([])
  })
})

