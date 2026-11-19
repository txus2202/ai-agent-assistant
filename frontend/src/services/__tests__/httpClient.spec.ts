import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { HttpClient, HttpError, formatHttpErrorDetail } from '../httpClient'

describe('HttpClient', () => {
  let client: HttpClient

  beforeEach(() => {
    client = new HttpClient()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('prepends configured baseUrl, injects Bearer JWT when provided, and sends JSON payload', async () => {
    client.configure({
      baseUrl: 'https://api.atenea.local/',
      getAccessToken: () => 'jwt-abc-123',
    })

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const res = await client.post<{ ok: boolean }>('/api/learning/session', { session_id: 's1' })

    expect(res).toEqual({ ok: true })
    expect(fetchMock).toHaveBeenCalledWith('https://api.atenea.local/api/learning/session', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer jwt-abc-123',
      },
      body: JSON.stringify({ session_id: 's1' }),
    })
  })

  it('leaves absolute URLs untouched and handles FormData without forcing Content-Type', async () => {
    client.configure({ baseUrl: 'https://api.atenea.local' })
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ text: 'hola' }), { status: 200 }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const formData = new FormData()
    formData.append('file', new Blob(['abc']), 'audio.webm')
    const out = await client.postFormData<{ text: string }>('https://other.host/upload', formData)

    expect(out).toEqual({ text: 'hola' })
    expect(fetchMock).toHaveBeenCalledWith('https://other.host/upload', {
      method: 'POST',
      credentials: 'same-origin',
      body: formData,
    })
  })

  it('throws typed HttpError parsing string and array validation details', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: 'Invalid credentials' }), { status: 401 }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ detail: [{ msg: 'Field required' }, { msg: 'Too short' }] }),
          { status: 422 },
        ),
      )
    vi.stubGlobal('fetch', fetchMock)

    await expect(client.get('/api/protected')).rejects.toMatchObject({
      name: 'HttpError',
      status: 401,
      message: 'Invalid credentials',
    })

    const caughtError = await client.post('/api/items', {}).catch((error: unknown) => error)
    expect(caughtError).toBeInstanceOf(HttpError)
    expect(caughtError).toMatchObject({
      status: 422,
      message: 'Field required, Too short',
    })
  })

  it('triggers onUnauthorized on 401 unless skipUnauthorizedHandler is true', async () => {
    const onUnauthorized = vi.fn()
    client.configure({ onUnauthorized })

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: 'Auth required' }), { status: 401 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: 'Bad creds' }), { status: 401 }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(client.get('/api/users')).rejects.toBeInstanceOf(HttpError)
    expect(onUnauthorized).toHaveBeenCalledWith({ url: '/api/users', status: 401 })

    onUnauthorized.mockClear()
    await expect(
      client.post('/api/auth/login', { username: 'u', password: 'p' }, { skipUnauthorizedHandler: true }),
    ).rejects.toBeInstanceOf(HttpError)
    expect(onUnauthorized).not.toHaveBeenCalled()
  })

  it('attempts single-flight refreshSession on concurrent 401 responses and retries requests', async () => {
    let token = 'expired-token'
    const refreshSession = vi.fn(async () => {
      token = 'fresh-token'
      return true
    })
    const onUnauthorized = vi.fn()

    client.configure({
      getAccessToken: () => token,
      refreshSession,
      onUnauthorized,
    })

    const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
      const authHeader = (init?.headers as Record<string, string> | undefined)?.Authorization
      if (authHeader === 'Bearer fresh-token') {
        return new Response(JSON.stringify({ ok: true }), { status: 200 })
      }
      return new Response(JSON.stringify({ detail: 'Expired' }), { status: 401 })
    })
    vi.stubGlobal('fetch', fetchMock)

    const [r1, r2] = await Promise.all([
      client.get<{ ok: boolean }>('/api/one'),
      client.get<{ ok: boolean }>('/api/two'),
    ])

    expect(r1).toEqual({ ok: true })
    expect(r2).toEqual({ ok: true })
    expect(refreshSession).toHaveBeenCalledTimes(1)
    expect(onUnauthorized).not.toHaveBeenCalled()
  })

  it('invokes onUnauthorized if refreshSession fails', async () => {
    const refreshSession = vi.fn().mockResolvedValue(false)
    const onUnauthorized = vi.fn()
    client.configure({ refreshSession, onUnauthorized })

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Expired' }), { status: 401 })),
    )

    await expect(client.get('/api/me')).rejects.toBeInstanceOf(HttpError)
    expect(refreshSession).toHaveBeenCalledTimes(1)
    expect(onUnauthorized).toHaveBeenCalledWith({ url: '/api/me', status: 401 })
  })

  it('reads binary responses via requestArrayBuffer and formats error fallback', async () => {
    const buf = new ArrayBuffer(8)
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        headers: new Headers(),
        arrayBuffer: () => Promise.resolve(buf),
      }),
    )

    const result = await client.requestArrayBuffer('/api/audio/synthesize', {
      method: 'POST',
      json: { text: 'hola' },
    })

    expect(result).toBe(buf)
    expect(formatHttpErrorDetail(undefined, 'Fallback message')).toBe('Fallback message')
  })
})
