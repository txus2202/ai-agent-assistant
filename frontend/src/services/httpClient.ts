export interface UnauthorizedContext {
  url: string
  status: number
}

export interface HttpClientConfig {
  baseUrl?: string
  credentials?: RequestCredentials
  getAccessToken?: () => string | null
  refreshSession?: () => Promise<boolean>
  onUnauthorized?: (context: UnauthorizedContext) => void
}

export interface HttpRequestOptions {
  method?: string
  headers?: Record<string, string>
  body?: BodyInit | null
  json?: unknown
  signal?: AbortSignal
  credentials?: RequestCredentials
  skipUnauthorizedHandler?: boolean
  skipRefreshRetry?: boolean
}

export interface HttpResponse<T> {
  data: T
  status: number
  headers: Headers | undefined
}

export function formatHttpErrorDetail(detail: unknown, fallback: string): string {
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

export class HttpError extends Error {
  readonly status: number
  readonly detail: unknown
  readonly payload: unknown

  constructor(message: string, status: number, detail: unknown = null, payload: unknown = null) {
    super(message)
    this.name = 'HttpError'
    this.status = status
    this.detail = detail
    this.payload = payload
  }
}

async function safeParseJson(response: Response): Promise<unknown> {
  if (typeof response.json !== 'function') {
    return null
  }
  try {
    return await response.json()
  } catch {
    return null
  }
}

function extractDetail(payload: unknown): unknown {
  if (typeof payload === 'object' && payload !== null && 'detail' in payload) {
    return (payload as { detail: unknown }).detail
  }
  return null
}

function stripTrailingSlashes(value: string): string {
  let end = value.length
  while (end > 0 && value[end - 1] === '/') {
    end--
  }
  return value.slice(0, end)
}

export class HttpClient {
  private baseUrl = ''
  private credentials: RequestCredentials = 'same-origin'
  private getAccessToken: (() => string | null) | undefined
  private refreshSession: (() => Promise<boolean>) | undefined
  private onUnauthorized: ((context: UnauthorizedContext) => void) | undefined
  private pendingRefresh: Promise<boolean> | null = null

  configure(config: Partial<HttpClientConfig>): void {
    if (config.baseUrl !== undefined) {
      this.baseUrl = stripTrailingSlashes(config.baseUrl)
    }
    if (config.credentials !== undefined) {
      this.credentials = config.credentials
    }
    if ('getAccessToken' in config) {
      this.getAccessToken = config.getAccessToken
    }
    if ('refreshSession' in config) {
      this.refreshSession = config.refreshSession
    }
    if ('onUnauthorized' in config) {
      this.onUnauthorized = config.onUnauthorized
    }
  }

  resetConfig(): void {
    this.baseUrl = ''
    this.credentials = 'same-origin'
    this.getAccessToken = undefined
    this.refreshSession = undefined
    this.onUnauthorized = undefined
    this.pendingRefresh = null
  }

  buildUrl(path: string): string {
    if (/^https?:\/\//i.test(path)) {
      return path
    }
    if (!this.baseUrl) {
      return path
    }
    const normalizedPath = path.startsWith('/') ? path : `/${path}`
    return `${this.baseUrl}${normalizedPath}`
  }

  private buildHeaders(options: HttpRequestOptions): Record<string, string> {
    const headers: Record<string, string> = { ...options.headers }
    if (options.json !== undefined && !('Content-Type' in headers)) {
      headers['Content-Type'] = 'application/json'
    }
    const token = this.getAccessToken?.()
    if (token && !('Authorization' in headers)) {
      headers.Authorization = `Bearer ${token}`
    }
    return headers
  }

  private async tryRefreshOnce(): Promise<boolean> {
    if (!this.refreshSession) {
      return false
    }
    this.pendingRefresh ??= this.refreshSession()
      .catch(() => false)
      .finally(() => {
        this.pendingRefresh = null
      })
    return this.pendingRefresh
  }

  async requestRaw(path: string, options: HttpRequestOptions = {}): Promise<Response> {
    const url = this.buildUrl(path)
    const headers = this.buildHeaders(options)
    const body = options.json !== undefined ? JSON.stringify(options.json) : options.body

    const init: RequestInit = {
      method: options.method ?? 'GET',
      credentials: options.credentials ?? this.credentials,
    }
    if (Object.keys(headers).length > 0) {
      init.headers = headers
    }
    if (body !== undefined) {
      init.body = body
    }
    if (options.signal !== undefined) {
      init.signal = options.signal
    }

    const response = await fetch(url, init)

    if (response.status === 401 && !options.skipRefreshRetry && this.refreshSession) {
      const refreshed = await this.tryRefreshOnce()
      if (refreshed) {
        return this.requestRaw(path, { ...options, skipRefreshRetry: true })
      }
    }

    if (response.status === 401 && !options.skipUnauthorizedHandler) {
      this.onUnauthorized?.({ url, status: 401 })
    }

    if (!response.ok) {
      const payload = await safeParseJson(response)
      const detail = extractDetail(payload)
      const status = typeof response.status === 'number' ? response.status : 500
      const message = formatHttpErrorDetail(detail, `HTTP error ${status}`)
      throw new HttpError(message, status, detail, payload)
    }

    return response
  }

  async requestJsonWithMeta<T>(path: string, options: HttpRequestOptions = {}): Promise<HttpResponse<T>> {
    const response = await this.requestRaw(path, options)
    const data = (await safeParseJson(response)) as T
    const status = typeof response.status === 'number' ? response.status : 200
    return {
      data,
      status,
      headers: response.headers,
    }
  }

  async requestJson<T>(path: string, options: HttpRequestOptions = {}): Promise<T> {
    const { data } = await this.requestJsonWithMeta<T>(path, options)
    return data
  }

  async requestArrayBuffer(path: string, options: HttpRequestOptions = {}): Promise<ArrayBuffer> {
    const response = await this.requestRaw(path, options)
    return response.arrayBuffer()
  }

  get<T>(path: string, options: Omit<HttpRequestOptions, 'method'> = {}): Promise<T> {
    return this.requestJson<T>(path, { ...options, method: 'GET' })
  }

  getWithMeta<T>(path: string, options: Omit<HttpRequestOptions, 'method'> = {}): Promise<HttpResponse<T>> {
    return this.requestJsonWithMeta<T>(path, { ...options, method: 'GET' })
  }

  post<T>(path: string, jsonBody?: unknown, options: Omit<HttpRequestOptions, 'method' | 'json'> = {}): Promise<T> {
    return this.requestJson<T>(path, { ...options, method: 'POST', json: jsonBody })
  }

  put<T>(path: string, jsonBody?: unknown, options: Omit<HttpRequestOptions, 'method' | 'json'> = {}): Promise<T> {
    return this.requestJson<T>(path, { ...options, method: 'PUT', json: jsonBody })
  }

  patch<T>(path: string, jsonBody?: unknown, options: Omit<HttpRequestOptions, 'method' | 'json'> = {}): Promise<T> {
    return this.requestJson<T>(path, { ...options, method: 'PATCH', json: jsonBody })
  }

  delete<T>(path: string, options: Omit<HttpRequestOptions, 'method'> = {}): Promise<T> {
    return this.requestJson<T>(path, { ...options, method: 'DELETE' })
  }

  postFormData<T>(path: string, formData: FormData, options: Omit<HttpRequestOptions, 'method' | 'body' | 'json'> = {}): Promise<T> {
    return this.requestJson<T>(path, { ...options, method: 'POST', body: formData })
  }
}

export const httpClient = new HttpClient()
