import { httpClient } from './httpClient'

export interface User {
  id: string
  username: string
  is_admin: boolean
  is_active: boolean
  created_at: string
  deleted_at?: string | null
}

export interface AuthStatusResponse {
  initialized: boolean
  authenticated?: boolean
  setup_token_required?: boolean
  user?: User | null
}

export interface AuthSessionResponse {
  token?: string
  user: User
}

export interface ChangePasswordPayload {
  current_password: string
  new_password: string
}

export interface CreateUserPayload {
  username: string
  password: string
  is_admin: boolean
}

export interface UpdateUserPayload {
  is_admin?: boolean
  is_active?: boolean
  password?: string
}

export interface DeleteUserResponse {
  message?: string
  strategy?: string
}

export const authService = {
  getStatus(): Promise<AuthStatusResponse> {
    return httpClient.get<AuthStatusResponse>('/api/auth/status', {
      skipUnauthorizedHandler: true,
    })
  },

  login(username: string, password: string): Promise<AuthSessionResponse> {
    return httpClient.post<AuthSessionResponse>(
      '/api/auth/login',
      { username, password },
      { skipUnauthorizedHandler: true },
    )
  },

  setupInitialAdmin(username: string, password: string, setupToken?: string): Promise<AuthSessionResponse> {
    const headers: Record<string, string> = {}
    const payload: Record<string, string> = { username, password }
    if (setupToken) {
      headers['X-Setup-Token'] = setupToken
      payload.setup_token = setupToken
    }
    return httpClient.post<AuthSessionResponse>('/api/auth/setup', payload, {
      headers,
    })
  },

  changePassword(payload: ChangePasswordPayload): Promise<{ ok?: boolean; message?: string }> {
    return httpClient.post<{ ok?: boolean; message?: string }>('/api/auth/change-password', payload, {
      skipUnauthorizedHandler: true,
    })
  },

  logout(): Promise<{ message?: string }> {
    return httpClient.post<{ message?: string }>('/api/auth/logout')
  },

  fetchUsers(): Promise<User[]> {
    return httpClient.get<User[]>('/api/auth/users')
  },

  createUser(payload: CreateUserPayload): Promise<User> {
    return httpClient.post<User>('/api/auth/users', payload)
  },

  updateUser(userId: string, updates: UpdateUserPayload): Promise<User> {
    return httpClient.patch<User>(`/api/auth/users/${encodeURIComponent(userId)}`, updates)
  },

  deleteUser(userId: string): Promise<DeleteUserResponse> {
    return httpClient.delete<DeleteUserResponse>(`/api/auth/users/${encodeURIComponent(userId)}`)
  },
}

