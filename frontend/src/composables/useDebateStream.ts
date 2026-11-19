import type { ComputedRef, Ref } from 'vue'
import { debateApiService } from '../services/debateApiService'
import { createDebateWsClient } from '../services/debateWsClient'
import { createDebateEventProcessor } from '../utils/debateEventProcessor'
import {
  normalizeAgentRole,
  resolveHitlUserMessage,
  type Agent,
  type ChatMessage,
  type DebateSession,
  type HitlDecisionType,
  type SupervisorEvent,
} from '../utils/debateHelpers'

export interface UseDebateStreamDeps {
  isConnected: Ref<boolean>
  isDebating: Ref<boolean>
  isHitlRequired: Ref<boolean>
  hitlCheckpoint: Ref<string | null>
  hitlTargetAgents: Ref<string[]>
  currentSessionId: Ref<string | null>
  messages: Ref<ChatMessage[]>
  rawEvents: Ref<SupervisorEvent[]>
  agents: Ref<Agent[]>
  executionTrail: Ref<string[]>
  projectName: ComputedRef<string>
  sessionTotalTokens: Ref<number>
  sessionCachedTokens: Ref<number>
  streamingMessageId: Ref<string | null>
  findAgent: (role?: string | null) => Agent | undefined
  resolveAgentDisplay: (role?: string | null) => {
    agentRole: string
    agentName: string
    colorHex: string
  }
  getKnownAgentNames: () => string[]
  recordExecutionTrail: (name?: string | null) => void
  isAgentReading: (role?: string | null) => boolean
  stopTts: () => void
  feedTtsStreamingChunk: (chunk: string, role?: string) => void
  flushTtsStreamingBuffer: (role?: string) => void
  resetTtsStreamState: () => void
  clearTtsStreamBuffer: () => void
  resetWakeWordSession: () => void
}

const MAX_RECONNECT_ATTEMPTS = 8
const AUTH_WS_CLOSE_CODES = new Set([1008, 4001, 4003])

export function useDebateStream(deps: UseDebateStreamDeps) {
  const processor = createDebateEventProcessor(deps)
  const debateWsClient = createDebateWsClient()
  let reconnectAttempts = 0
  let reconnectTimeout: ReturnType<typeof setTimeout> | null = null
  let shouldReconnect = true
  let shouldResyncOnOpen = false

  async function resyncSessionFromHistory(sessionId: string) {
    try {
      const session = (await debateApiService.getDebateSession(sessionId)) as DebateSession
      if (Array.isArray(session.events) && session.events.length > deps.rawEvents.value.length) {
        processor.loadDebate(session)
      } else if (session.status && session.status !== 'running' && deps.isDebating.value) {
        deps.isDebating.value = false
        processor.resetActiveAgentsToStandby()
      }
    } catch {
      // Best-effort sync after WebSocket reconnection
    }
  }

  function attemptReconnect() {
    if (!shouldReconnect) return
    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout)
      reconnectTimeout = null
    }
    if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      shouldReconnect = false
      console.warn(`[WS] Max reconnection attempts (${MAX_RECONNECT_ATTEMPTS}) reached`)
      return
    }

    const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 10000)
    console.log(`[WS] Attempting to reconnect in ${delay}ms...`)

    reconnectTimeout = setTimeout(() => {
      reconnectAttempts++
      connect()
    }, delay)
  }

  function connect() {
    shouldReconnect = true
    if (debateWsClient.isOpenOrConnecting()) {
      return
    }

    const wsUrl = debateWsClient.connect({
      onOpen: () => {
        console.log('[WS] Connected to', wsUrl)
        deps.isConnected.value = true
        reconnectAttempts = 0
        if (shouldResyncOnOpen && deps.currentSessionId.value) {
          shouldResyncOnOpen = false
          void resyncSessionFromHistory(deps.currentSessionId.value)
        } else {
          shouldResyncOnOpen = false
        }
      },
      onMessage: (rawData) => {
        try {
          const data = JSON.parse(rawData) as SupervisorEvent
          if (!data.timestamp) {
            data.timestamp = new Date().toISOString()
          }
          deps.rawEvents.value.push(data.id ? data : { ...data, id: processor.nextStableId('evt') })
          processor.handleSupervisorEvent(data)
        } catch {
          console.error('[WS] Failed to parse message', rawData)
        }
      },
      onClose: (closeEvent?: CloseEvent) => {
        console.log('[WS] Disconnected')
        const wasDebating = deps.isDebating.value
        deps.isConnected.value = false
        if (wasDebating) {
          processor.handleError({
            type: 'error',
            content: 'Conexión interrumpida con el servidor de agentes.',
          })
        }

        const closeCode = closeEvent?.code
        if (closeCode !== undefined && AUTH_WS_CLOSE_CODES.has(closeCode)) {
          shouldReconnect = false
          shouldResyncOnOpen = false
          return
        }

        if (shouldReconnect && wasDebating && deps.currentSessionId.value) {
          shouldResyncOnOpen = true
        }

        if (shouldReconnect) {
          attemptReconnect()
        }
      },
      onError: (error) => {
        console.error('[WS] Error', error)
        if (deps.isDebating.value) {
          processor.handleError({
            type: 'error',
            content: 'Error de comunicación WebSocket con el servidor.',
          })
        }
      },
    })
  }

  function disconnect() {
    shouldReconnect = false
    shouldResyncOnOpen = false
    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout)
      reconnectTimeout = null
    }
    reconnectAttempts = 0
    debateWsClient.disconnect()
    deps.isConnected.value = false
  }

  function startDebate(
    userRequest: string,
    targetAgent: string | string[] = 'supervisor',
    attachmentUrl: string | string[] | null = null,
    targetDomain?: string | null,
  ) {
    deps.stopTts()

    if (!deps.isConnected.value || !debateWsClient.hasSocket()) {
      deps.messages.value.push({
        id: processor.nextStableId('msg'),
        role: 'assistant',
        content: 'Error: Cannot start debate, disconnected from server. Trying to reconnect...',
      })
      connect()
      return
    }

    if (!deps.currentSessionId.value) {
      deps.currentSessionId.value = crypto.randomUUID()
      deps.sessionTotalTokens.value = 0
      deps.sessionCachedTokens.value = 0
    }

    const targetAgentsList = Array.isArray(targetAgent)
      ? targetAgent.length > 0
        ? targetAgent
        : ['supervisor']
      : [targetAgent || 'supervisor']
    const primaryTarget = targetAgentsList[0] || 'supervisor'

    deps.agents.value.forEach((a) => {
      a.state = 'STANDBY'
    })
    targetAgentsList.forEach((role) => {
      const startingAgent = processor.resolveTargetAgentOrSupervisor(role)
      if (startingAgent) {
        startingAgent.state = 'ACTIVE'
        startingAgent.startedAt = Date.now()
        startingAgent.turns = (startingAgent.turns || 0) + 1
      }
    })

    const isSupervisorTargeted = targetAgentsList.some((role) => {
      const n = normalizeAgentRole(role)
      return n === 'supervisor' || n === 'atenea'
    })

    if (isSupervisorTargeted || targetAgentsList.length === 0) {
      deps.executionTrail.value = ['Atenea']
    } else {
      const firstTargetName = deps.findAgent(primaryTarget)?.name || primaryTarget
      deps.executionTrail.value = [firstTargetName]
    }

    const history = deps.messages.value.slice(-10).map((m) => ({
      role: m.role,
      content: m.content,
      agent: m.agentName || m.agentRole,
    }))

    deps.isDebating.value = true
    deps.messages.value.push({
      id: crypto.randomUUID(),
      role: 'user',
      content: userRequest,
      timestamp: new Date().toISOString(),
    })

    let attachments: string[] = []
    if (Array.isArray(attachmentUrl)) {
      attachments = attachmentUrl
    } else if (attachmentUrl) {
      attachments = [attachmentUrl]
    }

    const payload: Record<string, unknown> = {
      type: 'start',
      session_id: deps.currentSessionId.value,
      user_request: userRequest,
      target_agent: primaryTarget,
      attachments,
      history,
    }
    if (targetDomain) {
      payload.target_domain = targetDomain
    }
    if (Array.isArray(targetAgent)) {
      payload.target_agents = targetAgentsList
    }
    debateWsClient.sendJson(payload)
  }

  function cancelDebate() {
    if (!deps.isDebating.value) return

    deps.stopTts()

    deps.agents.value.forEach((a) => {
      if (a.state === 'ACTIVE') {
        if (a.startedAt && !a.latency) {
          a.latency = Number(((Date.now() - a.startedAt) / 1000).toFixed(2))
        }
        a.state = 'STANDBY'
      }
    })

    deps.isDebating.value = false
    deps.isHitlRequired.value = false
    deps.hitlCheckpoint.value = null
    deps.hitlTargetAgents.value = []

    if (debateWsClient.hasSocket()) {
      try {
        debateWsClient.sendJson({ type: 'cancel' })
      } catch (e) {
        console.warn('Failed to send cancel over WebSocket:', e)
      }
      disconnect()
      connect()
    }

    deps.messages.value.push({
      id: crypto.randomUUID(),
      role: 'assistant',
      agentName: deps.projectName.value,
      agentRole: 'supervisor',
      content:
        '⚠️ Deliberación cancelada por el usuario. Puedes reformular tu consulta o iniciar una nueva cuando desees.',
      timestamp: new Date().toISOString(),
    })
  }

  function submitHitlDecision(
    decision: HitlDecisionType,
    feedback?: string,
    targetAgents?: string[],
  ) {
    deps.stopTts()
    deps.isHitlRequired.value = false
    processor.completeCheckpointAgent(deps.hitlCheckpoint.value)
    deps.hitlCheckpoint.value = null
    deps.resetWakeWordSession()

    const effectiveTargets = targetAgents ?? [...deps.hitlTargetAgents.value]
    deps.hitlTargetAgents.value = []

    const userMessageContent = resolveHitlUserMessage(decision, feedback, effectiveTargets)
    if (userMessageContent) {
      deps.messages.value.push({
        id: crypto.randomUUID(),
        role: 'user',
        content: userMessageContent,
        timestamp: new Date().toISOString(),
      })
    }

    const payload: {
      type: string
      decision: HitlDecisionType
      feedback: string
      target_agents?: string[]
    } = {
      type: 'hitl_response',
      decision,
      feedback: feedback || '',
    }
    if (effectiveTargets?.length) {
      payload.target_agents = effectiveTargets
    }
    debateWsClient.sendJson(payload)
  }

  return {
    connect,
    disconnect,
    clearSession: processor.clearSession,
    loadDebate: processor.loadDebate,
    startDebate,
    cancelDebate,
    handleSupervisorEvent: processor.handleSupervisorEvent,
    submitHitlDecision,
    get rawSocket() {
      return debateWsClient.rawSocket
    },
  }
}
