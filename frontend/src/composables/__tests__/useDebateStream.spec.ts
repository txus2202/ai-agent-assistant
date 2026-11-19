import { computed, ref } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { debateApiService } from '../../services/debateApiService'
import type { Agent, ChatMessage, SupervisorEvent } from '../../utils/debateHelpers'
import { useDebateStream } from '../useDebateStream'

interface MockSocket {
  readyState: number
  send: ReturnType<typeof vi.fn>
  close: ReturnType<typeof vi.fn>
  onopen: (() => void) | null
  onclose: ((ev?: CloseEvent) => void) | null
  onmessage: ((ev: { data: string }) => void) | null
  onerror: ((ev: Event) => void) | null
}

describe('useDebateStream', () => {
  let originalWebSocket: typeof WebSocket
  let sockets: MockSocket[] = []

  const buildStream = () => {
    const agents = ref<Agent[]>([
      { role: 'supervisor', name: 'Atenea', state: 'STANDBY' },
      { role: 'senior_architect', name: 'Hestia', state: 'STANDBY' },
    ])
    const isConnected = ref(false)
    const isDebating = ref(false)
    const isHitlRequired = ref(false)
    const hitlCheckpoint = ref<string | null>(null)
    const hitlTargetAgents = ref<string[]>([])
    const currentSessionId = ref<string | null>(null)
    const messages = ref<ChatMessage[]>([])
    const rawEvents = ref<SupervisorEvent[]>([])
    const executionTrail = ref<string[]>([])
    const projectName = computed(() => 'A.T.E.N.E.A.')
    const sessionTotalTokens = ref(0)
    const sessionCachedTokens = ref(0)
    const streamingMessageId = ref<string | null>(null)

    const stream = useDebateStream({
      isConnected,
      isDebating,
      isHitlRequired,
      hitlCheckpoint,
      hitlTargetAgents,
      currentSessionId,
      messages,
      rawEvents,
      agents,
      executionTrail,
      projectName,
      sessionTotalTokens,
      sessionCachedTokens,
      streamingMessageId,
      findAgent: (role) => agents.value.find((a) => a.role === role || a.name === role),
      resolveAgentDisplay: (role) => ({
        agentRole: role || 'supervisor',
        agentName: role === 'senior_architect' ? 'Hestia' : 'Atenea',
        colorHex: '#00e5ff',
      }),
      getKnownAgentNames: () => agents.value.map((a) => a.name),
      recordExecutionTrail: (name) => {
        if (name && executionTrail.value.at(-1) !== name) {
          executionTrail.value.push(name)
        }
      },
      isAgentReading: () => false,
      stopTts: vi.fn(),
      feedTtsStreamingChunk: vi.fn(),
      flushTtsStreamingBuffer: vi.fn(),
      resetTtsStreamState: vi.fn(),
      clearTtsStreamBuffer: vi.fn(),
      resetWakeWordSession: vi.fn(),
    })

    return { stream, isConnected, isDebating, isHitlRequired, currentSessionId, messages }
  }

  beforeEach(() => {
    vi.useFakeTimers()
    originalWebSocket = globalThis.WebSocket
    sockets = []
    class FakeWs {
      readyState = WebSocket.OPEN
      send = vi.fn()
      close = vi.fn()
      onopen: (() => void) | null = null
      onclose: ((ev?: CloseEvent) => void) | null = null
      onmessage: ((ev: { data: string }) => void) | null = null
      onerror: ((ev: Event) => void) | null = null
      constructor() {
        sockets.push(this)
      }
    }
    globalThis.WebSocket = FakeWs as unknown as typeof WebSocket
  })

  afterEach(() => {
    globalThis.WebSocket = originalWebSocket
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('stops reconnecting on auth close codes (4001) and resyncs session on normal drop', async () => {
    const getSessionSpy = vi.spyOn(debateApiService, 'getDebateSession').mockResolvedValue({
      id: 's-1',
      status: 'completed',
      events: [{ type: 'done', role: 'supervisor', content: 'Dictamen resincronizado.' }],
    })

    const ctx = buildStream()
    ctx.stream.connect()
    sockets[0]?.onopen?.()
    expect(ctx.isConnected.value).toBe(true)

    // Unexpected 1006 drop while debating -> reconnects and resyncs
    ctx.currentSessionId.value = 's-1'
    ctx.isDebating.value = true
    sockets[0]?.onclose?.({ code: 1006 } as CloseEvent)
    vi.advanceTimersByTime(1100)
    expect(sockets).toHaveLength(2)

    sockets[1]?.onopen?.()
    await Promise.resolve()
    await Promise.resolve()
    expect(getSessionSpy).toHaveBeenCalledWith('s-1')
    expect(ctx.messages.value.some((m) => m.content.includes('Dictamen resincronizado'))).toBe(true)

    // Auth error close code 4001 -> must NOT schedule reconnect
    sockets[1]?.onclose?.({ code: 4001 } as CloseEvent)
    vi.advanceTimersByTime(10000)
    expect(sockets).toHaveLength(2)
  })

  it('starts, cancels, and submits HITL decisions cleanly over WebSocket', () => {
    const ctx = buildStream()
    ctx.stream.connect()
    sockets[0]?.onopen?.()

    ctx.stream.startDebate('Analizar arquitectura', ['senior_architect'])
    expect(ctx.isDebating.value).toBe(true)
    expect(sockets[0]?.send).toHaveBeenCalledTimes(1)

    ctx.stream.submitHitlDecision('approve', '', ['senior_architect'])
    expect(ctx.isHitlRequired.value).toBe(false)
    expect(sockets[0]?.send).toHaveBeenCalledWith(
      JSON.stringify({
        type: 'hitl_response',
        decision: 'approve',
        feedback: '',
        target_agents: ['senior_architect'],
      }),
    )

    ctx.stream.cancelDebate()
    expect(ctx.isDebating.value).toBe(false)
    expect(ctx.messages.value.at(-1)?.content).toContain('Deliberación cancelada')
  })
})

