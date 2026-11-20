import type { Ref } from 'vue'
import {
  applyAgentLatencyFromEvent,
  applyAgentTokensFromEvent,
  buildCompletionDedupKey,
  cleanAgentMessageContent,
  createStableIdGenerator,
  hasAuthoritativeTokenMetadata,
  normalizeAgentRole,
  stripFailedBlocksFromHitlContent,
  type Agent,
  type ChatMessage,
  type DebateSession,
  type SupervisorEvent,
} from './debateHelpers'

export interface DebateEventProcessorDeps {
  isDebating: Ref<boolean>
  isHitlRequired: Ref<boolean>
  hitlCheckpoint: Ref<string | null>
  hitlTargetAgents: Ref<string[]>
  currentSessionId: Ref<string | null>
  messages: Ref<ChatMessage[]>
  rawEvents: Ref<SupervisorEvent[]>
  agents: Ref<Agent[]>
  executionTrail: Ref<string[]>
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

export function createDebateEventProcessor(deps: DebateEventProcessorDeps) {
  const nextStableId = createStableIdGenerator()
  const streamedTokenEstimates: Record<string, { tokens: number; completionTokens: number }> = {}
  let lastCompletedTurnKey: string | null = null

  function resolveTargetAgentOrSupervisor(role?: string | null): Agent | undefined {
    return (
      deps.findAgent(role) ||
      (normalizeAgentRole(role) === 'supervisor' ? deps.findAgent('supervisor') : undefined)
    )
  }

  function pushRawEvent(event: SupervisorEvent) {
    if (event.id) {
      deps.rawEvents.value.push(event)
      return
    }
    deps.rawEvents.value.push({
      ...event,
      id: nextStableId('evt'),
    })
  }

  function clearStreamedEstimate(role?: string) {
    if (!role) {
      for (const k of Object.keys(streamedTokenEstimates)) {
        delete streamedTokenEstimates[k]
      }
      return
    }
    delete streamedTokenEstimates[role]
  }

  function reconcileStreamedEstimate(agent: Agent) {
    const est = streamedTokenEstimates[agent.role]
    if (!est) return
    agent.tokens = Math.max(0, (agent.tokens || 0) - est.tokens)
    agent.completionTokens = Math.max(0, (agent.completionTokens || 0) - est.completionTokens)
    deps.sessionTotalTokens.value = Math.max(0, deps.sessionTotalTokens.value - est.tokens)
    delete streamedTokenEstimates[agent.role]
  }

  function updateCachedTokens(event: SupervisorEvent) {
    if (event.metadata?.cached_tokens !== undefined) {
      const parsed = Number.parseInt(String(event.metadata.cached_tokens), 10)
      if (!Number.isNaN(parsed) && parsed > 0) {
        deps.sessionCachedTokens.value += parsed
      }
    }
  }

  function pushAgentMessage(content: string, role?: string | null) {
    const { agentRole, agentName, colorHex } = deps.resolveAgentDisplay(role)
    const cleanContent = cleanAgentMessageContent(content, deps.getKnownAgentNames())
    if (!cleanContent) return

    const lastMsg = deps.messages.value.at(-1)
    if (lastMsg?.role === 'assistant') {
      if (lastMsg.content === cleanContent || lastMsg.content === content) {
        return
      }
      const rawLast = lastMsg.content.replace(/^⚠️\s*/, '').trim()
      const rawNew = cleanContent.replace(/^⚠️\s*/, '').trim()
      if (rawLast && rawNew && (rawLast.includes(rawNew) || rawNew.includes(rawLast))) {
        return
      }
    }

    deps.messages.value.push({
      id: nextStableId('msg'),
      role: 'assistant',
      content: cleanContent,
      agentRole,
      agentName,
      colorHex,
    })
  }

  function completeCheckpointAgent(checkpoint: string | null) {
    if (!checkpoint) return
    const checkpointAgent = checkpoint.startsWith('after_')
      ? checkpoint.replace('after_', '')
      : checkpoint
    const ag = deps.findAgent(checkpointAgent)
    if (ag?.state === 'ACTIVE' && ag?.role !== 'supervisor') {
      ag.state = 'COMPLETED'
    }
  }

  function resetActiveAgentsToStandby() {
    deps.agents.value.forEach((a) => {
      if (a.state === 'ACTIVE') {
        if (a.startedAt) {
          a.latency = Number(((Date.now() - a.startedAt) / 1000).toFixed(2))
          a.startedAt = undefined
        }
        a.state = 'STANDBY'
      }
    })
  }

  function handleHitlRequired(event: SupervisorEvent) {
    deps.isHitlRequired.value = true
    const checkpoint = event.metadata?.checkpoint
    deps.hitlCheckpoint.value = checkpoint || null
    const checkpointAgent = checkpoint?.startsWith('after_')
      ? checkpoint.replace('after_', '')
      : undefined
    const metadataAgent = typeof event.metadata?.agent === 'string' ? event.metadata.agent : undefined
    const role = metadataAgent || event.role || checkpointAgent || 'Atenea'

    const rawContent = (event.content || '').trim()
    if (!rawContent || rawContent === 'HITL Required') {
      return
    }

    const contentToPush = stripFailedBlocksFromHitlContent(rawContent)
    if (contentToPush) {
      pushAgentMessage(contentToPush, role)
    }
  }

  function handleAgentStarted(event: SupervisorEvent) {
    const agent = resolveTargetAgentOrSupervisor(event.role)
    if (!agent) return

    if (agent.role !== 'supervisor') {
      const sup = deps.findAgent('supervisor')
      if (sup?.state === 'ACTIVE') {
        if (sup.startedAt) {
          sup.latency = Number(((Date.now() - sup.startedAt) / 1000).toFixed(2))
        }
        sup.state = 'STANDBY'
      }
    }

    clearStreamedEstimate(agent.role)
    lastCompletedTurnKey = null
    agent.state = 'ACTIVE'
    agent.turns = (agent.turns || 0) + 1
    agent.startedAt = Date.now()
    deps.recordExecutionTrail(agent.name)
  }

  function handleAgentCompleted(event: SupervisorEvent) {
    const agent = resolveTargetAgentOrSupervisor(event.role)
    if (!agent) return

    if (!deps.isAgentReading(agent.role)) {
      agent.state = 'COMPLETED'
    }
    if (hasAuthoritativeTokenMetadata(event)) {
      reconcileStreamedEstimate(agent)
    }
    applyAgentLatencyFromEvent(agent, event)
    const estTokens = applyAgentTokensFromEvent(agent, event)
    updateCachedTokens(event)
    deps.sessionTotalTokens.value += estTokens
    lastCompletedTurnKey = buildCompletionDedupKey(agent.role, event)
  }

  function handleStreamChunk(event: SupervisorEvent) {
    const { agentRole, agentName, colorHex } = deps.resolveAgentDisplay(event.role)
    const chunk = event.content || ''

    let targetMsg = deps.streamingMessageId.value
      ? deps.messages.value.find((m) => m.id === deps.streamingMessageId.value)
      : null

    if (!targetMsg) {
      const newId = crypto.randomUUID()
      deps.streamingMessageId.value = newId
      deps.resetTtsStreamState()
      targetMsg = {
        id: newId,
        role: 'assistant',
        content: chunk,
        agentRole,
        agentName,
        colorHex,
        isStreaming: true,
      }
      deps.messages.value.push(targetMsg)
    } else {
      targetMsg.content += chunk
    }

    const targetRole = agentRole || event.role || 'supervisor'
    const streamingAgent = deps.findAgent(targetRole)
    if (streamingAgent) {
      if (streamingAgent.state !== 'ACTIVE') {
        streamingAgent.state = 'ACTIVE'
      }
      const chunkTokens = Math.max(1, Math.round(chunk.length / 4))
      streamingAgent.completionTokens = (streamingAgent.completionTokens || 0) + chunkTokens
      streamingAgent.tokens = (streamingAgent.tokens || 0) + chunkTokens
      deps.sessionTotalTokens.value += chunkTokens
      const prevEst = streamedTokenEstimates[streamingAgent.role] || {
        tokens: 0,
        completionTokens: 0,
      }
      streamedTokenEstimates[streamingAgent.role] = {
        tokens: prevEst.tokens + chunkTokens,
        completionTokens: prevEst.completionTokens + chunkTokens,
      }
    }

    deps.feedTtsStreamingChunk(chunk, agentRole || event.role || undefined)
  }

  function markRemainingActiveAgentsDone() {
    deps.agents.value.forEach((a) => {
      if (a.state === 'ACTIVE' && !deps.isAgentReading(a.role)) {
        a.state = 'COMPLETED'
      }
    })
  }

  function updateDoneAgentMetrics(event: SupervisorEvent, doneRole: string): Agent | undefined {
    const targetAgent = resolveTargetAgentOrSupervisor(doneRole)
    if (!targetAgent) return undefined

    const isDuplicateCompanionDone =
      event.metadata?.metrics_reported === 'true' ||
      (lastCompletedTurnKey !== null &&
        buildCompletionDedupKey(targetAgent.role, event) === lastCompletedTurnKey)
    lastCompletedTurnKey = null

    if (isDuplicateCompanionDone) {
      if (!deps.isAgentReading(targetAgent.role)) {
        targetAgent.state = 'COMPLETED'
      }
      return targetAgent
    }

    if (event.metadata) {
      if (hasAuthoritativeTokenMetadata(event)) {
        reconcileStreamedEstimate(targetAgent)
      }
      applyAgentLatencyFromEvent(targetAgent, event)
      const estTokens = applyAgentTokensFromEvent(targetAgent, event)
      updateCachedTokens(event)
      deps.sessionTotalTokens.value += estTokens
    } else if (event.content && !streamedTokenEstimates[targetAgent.role]) {
      const words = event.content.trim().split(/\s+/).filter(Boolean).length
      const outTokens = Math.max(12, Math.round(words * 1.35))
      const inTokens = Math.max(25, Math.round(outTokens * 1.4))
      targetAgent.tokens = (targetAgent.tokens || 0) + outTokens + inTokens
      targetAgent.promptTokens = (targetAgent.promptTokens || 0) + inTokens
      targetAgent.completionTokens = (targetAgent.completionTokens || 0) + outTokens
      deps.sessionTotalTokens.value += outTokens + inTokens
    }
    targetAgent.turns = Math.max(1, (targetAgent.turns || 0) + 1)
    if (!deps.isAgentReading(targetAgent.role)) {
      targetAgent.state = 'COMPLETED'
    }
    return targetAgent
  }

  function finalizeDoneMessage(event: SupervisorEvent) {
    if (deps.streamingMessageId.value) {
      const targetMsg = deps.messages.value.find((m) => m.id === deps.streamingMessageId.value)
      if (targetMsg) {
        targetMsg.isStreaming = false
        if (event.content) {
          targetMsg.content = cleanAgentMessageContent(event.content, deps.getKnownAgentNames())
        }
      }
      deps.streamingMessageId.value = null
      deps.flushTtsStreamingBuffer(event.role || undefined)
    } else if (event.content?.trim()) {
      pushAgentMessage(event.content, event.role)
    }
  }

  function handleDone(event: SupervisorEvent) {
    deps.isDebating.value = false
    deps.resetWakeWordSession()
    markRemainingActiveAgentsDone()

    const doneRole = event.role || 'supervisor'
    const targetAgent = updateDoneAgentMetrics(event, doneRole)
    finalizeDoneMessage(event)

    const finalRoleNorm = normalizeAgentRole(doneRole)
    if (finalRoleNorm === 'supervisor' || finalRoleNorm === 'atenea') {
      deps.recordExecutionTrail('Atenea')
    } else {
      deps.recordExecutionTrail(targetAgent?.name || doneRole)
    }
  }

  function handleNonFatalAgentError(event: SupervisorEvent): boolean {
    const isFatal = event.metadata?.fatal !== 'false'
    if (isFatal || !event.role) {
      return false
    }

    const failedAgent = resolveTargetAgentOrSupervisor(event.role)
    if (failedAgent) {
      if (failedAgent.startedAt && !failedAgent.latency) {
        failedAgent.latency = Number(((Date.now() - failedAgent.startedAt) / 1000).toFixed(2))
      }
      failedAgent.startedAt = undefined
      failedAgent.state = 'ERROR'
    }

    const errorContent = `⚠️ ${event.content}`
    const lastMsg = deps.messages.value.at(-1)
    if (
      lastMsg?.role === 'assistant' &&
      (lastMsg.content === errorContent ||
        (Boolean(event.content) &&
          (lastMsg.content === event.content || lastMsg.content.includes(event.content!))))
    ) {
      return true
    }

    const { agentRole, agentName, colorHex } = deps.resolveAgentDisplay(event.role)
    deps.messages.value.push({
      id: nextStableId('msg'),
      role: 'assistant',
      content: errorContent,
      agentRole,
      agentName,
      colorHex,
    })
    return true
  }

  function handleError(event: SupervisorEvent) {
    if (handleNonFatalAgentError(event)) {
      return
    }

    deps.isDebating.value = false
    deps.streamingMessageId.value = null
    deps.clearTtsStreamBuffer()
    deps.stopTts()
    deps.resetWakeWordSession()

    resetActiveAgentsToStandby()

    const errorContent = `Error: ${event.content}`
    const lastMsg = deps.messages.value.at(-1)
    if (
      lastMsg?.role === 'assistant' &&
      (lastMsg.content === errorContent || lastMsg.content === event.content)
    ) {
      return
    }

    const { agentRole, agentName, colorHex } = deps.resolveAgentDisplay(event.role || 'supervisor')
    deps.messages.value.push({
      id: nextStableId('msg'),
      role: 'assistant',
      content: errorContent,
      agentRole,
      agentName,
      colorHex,
    })
  }

  function handleSupervisorEvent(event: SupervisorEvent) {
    switch (event.type) {
      case 'stream_chunk':
        handleStreamChunk(event)
        break
      case 'hitl_required':
        handleHitlRequired(event)
        break
      case 'agent_started':
        handleAgentStarted(event)
        break
      case 'agent_completed':
        handleAgentCompleted(event)
        break
      case 'done':
        handleDone(event)
        break
      case 'error':
        handleError(event)
        break
      case 'message':
        pushAgentMessage(event.content || '', event.role)
        break
      case 'user_message':
        deps.messages.value.push({
          id: crypto.randomUUID(),
          role: 'user',
          content: event.content || '',
          timestamp: new Date().toISOString(),
        })
        break
    }
  }

  function clearSession() {
    clearStreamedEstimate()
    lastCompletedTurnKey = null
    deps.messages.value = []
    deps.rawEvents.value = []
    deps.currentSessionId.value = null
    deps.sessionTotalTokens.value = 0
    deps.sessionCachedTokens.value = 0
    deps.isHitlRequired.value = false
    deps.hitlCheckpoint.value = null
    deps.hitlTargetAgents.value = []
    deps.isDebating.value = false
    deps.executionTrail.value = []
    deps.agents.value.forEach((a) => {
      a.state = 'STANDBY'
      a.tokens = 0
      a.promptTokens = 0
      a.completionTokens = 0
      a.latency = 0
      a.turns = 0
    })
  }

  function loadDebate(debate: DebateSession) {
    clearSession()
    if (debate.id) {
      deps.currentSessionId.value = debate.id
    }

    const hasUserMessageEvents =
      debate.events &&
      Array.isArray(debate.events) &&
      debate.events.some((e) => e.type === 'user_message')
    if (!hasUserMessageEvents && debate.user_request) {
      deps.messages.value.push({
        id: crypto.randomUUID(),
        role: 'user',
        content: debate.user_request,
        timestamp: new Date().toISOString(),
      })
    }

    if (debate.events && Array.isArray(debate.events)) {
      debate.events.forEach((event: SupervisorEvent) => {
        pushRawEvent(event)
        handleSupervisorEvent(event)
      })
    }

    deps.isDebating.value = debate.status === 'running'

    completeCheckpointAgent(deps.hitlCheckpoint.value)
    deps.isHitlRequired.value = false
    deps.hitlCheckpoint.value = null
    deps.hitlTargetAgents.value = []

    if (!deps.isDebating.value) {
      deps.agents.value.forEach((a) => {
        if (a.state === 'ACTIVE') {
          a.state = 'COMPLETED'
        }
      })
    }
  }

  return {
    nextStableId,
    resolveTargetAgentOrSupervisor,
    completeCheckpointAgent,
    resetActiveAgentsToStandby,
    handleError,
    handleSupervisorEvent,
    clearSession,
    loadDebate,
  }
}

