import { defineStore } from 'pinia'

export interface User {
  id: string
  username: string
  is_admin: boolean
  is_active: boolean
  created_at: string
  deleted_at?: string | null
}

interface AuthState {
  user: User | null
  users: User[]
  isInitialized: boolean | null
  setupTokenRequired: boolean
  isLoading: boolean
  usersLoading: boolean
  errorMessage: string | null
  adminError: string | null
}

function formatErrorDetail(detail: unknown, fallback: string): string {
  if (typeof detail === 'string') {
    return detail
  }
  if (Array.isArray(detail)) {
    return detail
      .map((item: unknown) => {
        if (typeof item === 'object' && item !== null && 'msg' in item) {
          return String((item as { msg: unknown }).msg)
        }
        return String(item)
      })
      .join(', ')
  }
  return fallback
}

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    user: null,
    users: [],
    isInitialized: null,
    setupTokenRequired: false,
    isLoading: false,
    usersLoading: false,
    errorMessage: null,
    adminError: null,
  }),

  getters: {
    isAuthenticated: (state): boolean => !!state.user,
    isAdmin: (state): boolean => !!state.user?.is_admin,
  },

  actions: {
    async checkAuth(): Promise<void> {
      this.isLoading = true
      this.errorMessage = null
      try {
        const statusRes = await fetch('/api/auth/status')
        if (statusRes.ok) {
          const statusData = await statusRes.json()
          this.isInitialized = statusData.initialized
          this.setupTokenRequired = !!statusData.setup_token_required
          this.user = statusData.user || null
        } else {
          this.isInitialized = false
          this.setupTokenRequired = false
          this.user = null
        }
      } catch (err) {
        console.error('Failed to check auth status:', err)
        this.user = null
      } finally {
        this.isLoading = false
      }
    },

    async login(username: string, password: string): Promise<boolean> {
      this.isLoading = true
      this.errorMessage = null
      try {
        const response = await fetch('/api/auth/login', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          credentials: 'same-origin',
          body: JSON.stringify({ username, password }),
        })

        const data = await response.json()
        if (response.ok) {
          this.user = data.user
          this.isInitialized = true
          return true
        } else {
          this.errorMessage = formatErrorDetail(data?.detail, 'Error al iniciar sesión')
          this.user = null
          return false
        }
      } catch (err: unknown) {
        this.errorMessage = err instanceof Error ? err.message : 'Error de conexión'
        this.user = null
        return false
      } finally {
        this.isLoading = false
      }
    },

    async setupInitialAdmin(username: string, password: string, setupToken?: string): Promise<boolean> {
      this.isLoading = true
      this.errorMessage = null
      try {
        const headers: Record<string, string> = {
          'Content-Type': 'application/json',
        }
        if (setupToken) {
          headers['X-Setup-Token'] = setupToken
        }
        const payload: Record<string, string> = { username, password }
        if (setupToken) {
          payload.setup_token = setupToken
        }
        const response = await fetch('/api/auth/setup', {
          method: 'POST',
          headers,
          credentials: 'same-origin',
          body: JSON.stringify(payload),
        })

        const data = await response.json()
        if (response.ok) {
          this.user = data.user
          this.isInitialized = true
          return true
        } else {
          this.errorMessage = formatErrorDetail(data?.detail, 'Error al configurar el administrador inicial')
          return false
        }
      } catch (err: unknown) {
        this.errorMessage = err instanceof Error ? err.message : 'Error de conexión'
        return false
      } finally {
        this.isLoading = false
      }
    },

    async changePassword(currentPassword: string, newPassword: string): Promise<boolean> {
      this.isLoading = true
      this.errorMessage = null
      try {
        const response = await fetch('/api/auth/change-password', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          credentials: 'same-origin',
          body: JSON.stringify({
            current_password: currentPassword,
            new_password: newPassword,
          }),
        })

        const data = await response.json()
        if (response.ok) {
          return true
        } else {
          this.errorMessage = formatErrorDetail(data?.detail, 'Error al cambiar la contraseña')
          return false
        }
      } catch (err: unknown) {
        this.errorMessage = err instanceof Error ? err.message : 'Error de conexión'
        return false
      } finally {
        this.isLoading = false
      }
    },

    async logout(): Promise<void> {
      try {
        await fetch('/api/auth/logout', {
          method: 'POST',
          credentials: 'same-origin',
        })
      } catch (err) {
        console.error('Logout error:', err)
      } finally {
        this.user = null
        this.users = []
      }
    },

    async fetchUsers(): Promise<User[]> {
      this.usersLoading = true
      this.adminError = null
      try {
        const response = await fetch('/api/auth/users', {
          credentials: 'same-origin',
        })
        if (response.ok) {
          const data: User[] = await response.json()
          this.users = data
          return data
        } else {
          const data = await response.json().catch(() => ({}))
          const msg = formatErrorDetail(data?.detail, 'Error al obtener la lista de usuarios')
          this.adminError = msg
          this.errorMessage = msg
          return []
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Error de conexión'
        this.adminError = msg
        this.errorMessage = msg
        return []
      } finally {
        this.usersLoading = false
      }
    },

    async createUser(
      username: string,
      password: string,
      isAdmin: boolean = false,
    ): Promise<User | null> {
      this.isLoading = true
      this.adminError = null
      try {
        const response = await fetch('/api/auth/users', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          credentials: 'same-origin',
          body: JSON.stringify({
            username,
            password,
            is_admin: isAdmin,
          }),
        })

        const data = await response.json()
        if (response.ok) {
          const newUser: User = data
          this.users.push(newUser)
          return newUser
        } else {
          const msg = formatErrorDetail(data?.detail, 'Error al crear el usuario')
          this.adminError = msg
          this.errorMessage = msg
          return null
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Error de conexión'
        this.adminError = msg
        this.errorMessage = msg
        return null
      } finally {
        this.isLoading = false
      }
    },

    async updateUser(
      userId: string,
      updates: { is_admin?: boolean; is_active?: boolean; password?: string },
    ): Promise<User | null> {
      this.isLoading = true
      this.adminError = null
      try {
        const response = await fetch(`/api/auth/users/${userId}`, {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
          },
          credentials: 'same-origin',
          body: JSON.stringify(updates),
        })

        const data = await response.json()
        if (response.ok) {
          const updatedUser: User = data
          const idx = this.users.findIndex((u) => u.id === userId)
          if (idx !== -1) {
            this.users[idx] = updatedUser
          }
          if (this.user?.id === userId) {
            this.user = updatedUser
          }
          return updatedUser
        } else {
          const msg = formatErrorDetail(data?.detail, 'Error al actualizar usuario')
          this.adminError = msg
          this.errorMessage = msg
          return null
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Error de conexión'
        this.adminError = msg
        this.errorMessage = msg
        return null
      } finally {
        this.isLoading = false
      }
    },

    async deleteUser(userId: string): Promise<{ success: boolean; strategy?: string }> {
      this.isLoading = true
      this.adminError = null
      try {
        const response = await fetch(`/api/auth/users/${userId}`, {
          method: 'DELETE',
          credentials: 'same-origin',
        })

        const data = await response.json()
        if (response.ok) {
          if (data.strategy === 'hard') {
            this.users = this.users.filter((u) => u.id !== userId)
          } else {
            const idx = this.users.findIndex((u) => u.id === userId)
            const existing = this.users[idx]
            if (existing) {
              this.users[idx] = {
                ...existing,
                is_active: false,
                deleted_at: new Date().toISOString(),
              }
            }
          }
          return { success: true, strategy: data.strategy }
        } else {
          const msg = formatErrorDetail(data?.detail, 'Error al eliminar usuario')
          this.adminError = msg
          this.errorMessage = msg
          return { success: false }
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Error de conexión'
        this.adminError = msg
        this.errorMessage = msg
        return { success: false }
      } finally {
        this.isLoading = false
      }
    },

    clearAdminError(): void {
      this.adminError = null
    },
  },
})
