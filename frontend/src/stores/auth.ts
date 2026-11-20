import { defineStore } from 'pinia'
import { authService, type User } from '../services/authService'
import { HttpError, formatHttpErrorDetail } from '../services/httpClient'

export type { User } from '../services/authService'

interface AuthState {
  user: User | null
  users: User[]
  isInitialized: boolean | null
  isBackendAvailable: boolean | null
  setupTokenRequired: boolean
  isLoading: boolean
  usersLoading: boolean
  errorMessage: string | null
  adminError: string | null
}

function resolveErrorMessage(err: unknown, fallback: string): string {
  if (err instanceof HttpError) {
    return formatHttpErrorDetail(err.detail, fallback)
  }
  return err instanceof Error ? err.message : fallback
}

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    user: null,
    users: [],
    isInitialized: null,
    isBackendAvailable: null,
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
        const statusData = await authService.getStatus()
        this.isBackendAvailable = true
        this.isInitialized = statusData.initialized
        this.setupTokenRequired = !!statusData.setup_token_required
        this.user = statusData.user || null
      } catch (err) {
        this.isBackendAvailable = false
        this.isInitialized = null
        this.setupTokenRequired = false
        this.user = null
        if (err instanceof HttpError) {
          this.errorMessage = 'El servidor backend no está disponible en este momento.'
        } else {
          console.error('Failed to check auth status:', err)
          this.errorMessage = 'No se ha podido conectar con el servidor backend.'
        }
      } finally {
        this.isLoading = false
      }
    },

    async login(username: string, password: string): Promise<boolean> {
      this.isLoading = true
      this.errorMessage = null
      try {
        const data = await authService.login(username, password)
        this.user = data.user
        this.isInitialized = true
        return true
      } catch (err: unknown) {
        this.errorMessage = resolveErrorMessage(
          err,
          err instanceof HttpError ? 'Error al iniciar sesión' : 'Error de conexión',
        )
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
        const data = await authService.setupInitialAdmin(username, password, setupToken)
        this.user = data.user
        this.isInitialized = true
        return true
      } catch (err: unknown) {
        this.errorMessage = resolveErrorMessage(
          err,
          err instanceof HttpError ? 'Error al configurar el administrador inicial' : 'Error de conexión',
        )
        return false
      } finally {
        this.isLoading = false
      }
    },

    async changePassword(currentPassword: string, newPassword: string): Promise<boolean> {
      this.isLoading = true
      this.errorMessage = null
      try {
        await authService.changePassword({
          current_password: currentPassword,
          new_password: newPassword,
        })
        return true
      } catch (err: unknown) {
        this.errorMessage = resolveErrorMessage(
          err,
          err instanceof HttpError ? 'Error al cambiar la contraseña' : 'Error de conexión',
        )
        return false
      } finally {
        this.isLoading = false
      }
    },

    async logout(): Promise<void> {
      try {
        await authService.logout()
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
        const data = await authService.fetchUsers()
        this.users = data
        return data
      } catch (err: unknown) {
        const msg = resolveErrorMessage(
          err,
          err instanceof HttpError ? 'Error al obtener la lista de usuarios' : 'Error de conexión',
        )
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
        const newUser = await authService.createUser({
          username,
          password,
          is_admin: isAdmin,
        })
        this.users.push(newUser)
        return newUser
      } catch (err: unknown) {
        const msg = resolveErrorMessage(
          err,
          err instanceof HttpError ? 'Error al crear el usuario' : 'Error de conexión',
        )
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
        const updatedUser = await authService.updateUser(userId, updates)
        const idx = this.users.findIndex((u) => u.id === userId)
        if (idx !== -1) {
          this.users[idx] = updatedUser
        }
        if (this.user?.id === userId) {
          this.user = updatedUser
        }
        return updatedUser
      } catch (err: unknown) {
        const msg = resolveErrorMessage(
          err,
          err instanceof HttpError ? 'Error al actualizar usuario' : 'Error de conexión',
        )
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
        const data = await authService.deleteUser(userId)
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
      } catch (err: unknown) {
        const msg = resolveErrorMessage(
          err,
          err instanceof HttpError ? 'Error al eliminar usuario' : 'Error de conexión',
        )
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
