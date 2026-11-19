import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { configService, type DebateTopology } from '../services/configService'
import { debateApiService } from '../services/debateApiService'
import { formatHttpErrorDetail, HttpError } from '../services/httpClient'
import { createTtsAudioEngine } from '../composables/useTtsAudio'
import { useWakeWord } from '../composables/useWakeWord'
import { useDebateStream } from '../composables/useDebateStream'
import {
  cleanAgentMessageContent,
  normalizeAgentRole,
  resolveHitlUserMessage,
  type Agent,
  type ChatMessage,
  type SupervisorEvent,
} from '../utils/debateHelpers'
import { findSentenceSplitIndex, getToolSpokenFallback } from '../utils/ttsFilter'

export { resolveWsUrl } from '../services/wsClient'
export type { DebateTopology } from '../services/configService'
export type {
  Agent,
  AgentState,
  ChatMessage,
  DebateSession,
  HitlDecisionType,
  SupervisorEvent,
} from '../utils/debateHelpers'
export { cleanAgentMessageContent, normalizeAgentRole, resolveHitlUserMessage }
export { findSentenceSplitIndex, getToolSpokenFallback }

export async function uploadFile(file: File): Promise<string> {
  return debateApiService.uploadFile(file)
}

export const useDebateStore = defineStore('debate', () => {
  const isConnected = ref(false)
  const isDebating = ref(false)
  const isHitlRequired = ref(false)
  const hitlCheckpoint = ref<string | null>(null)
  const hitlTargetAgents = ref<string[]>([])
  const currentSessionId = ref<string | null>(null)
  const messages = ref<ChatMessage[]>([])
  const rawEvents = ref<SupervisorEvent[]>([])
  const draftMessage = ref('')
  const streamingMessageId = ref<string | null>(null)

  const agents = ref<Agent[]>([])
  const isAgentsLoaded = ref(false)
  const executionTrail = ref<string[]>([])
  const topology = ref<DebateTopology | null>(null)
  const projectName = computed(() => topology.value?.project_name || 'AI AGENT ASSISTANT')
  const projectDescription = computed(
    () => topology.value?.project_description || 'Asistente de IA Multi-Agente',
  )

  const sessionTotalTokens = ref(0)
  const sessionCachedTokens = ref(0)
  const cacheSavingsPercentage = computed(() => {
    const total = sessionTotalTokens.value + sessionCachedTokens.value
    if (total === 0) return 0
    return Math.min(100, Math.round((sessionCachedTokens.value / total) * 100))
  })

  const selectedAgent = ref<string>('supervisor')
  const selectedAgents = ref<string[]>(['supervisor'])
  const isLearningSession = ref(false)
  const learningStatusMessage = ref<string | null>(null)

  function recordExecutionTrail(name?: string | null) {
    if (!name) return
    const trail = executionTrail.value
    if (trail.at(-1) !== name) {
      executionTrail.value = [...trail, name]
    }
  }

  function findAgent(role?: string | null): Agent | undefined {
    if (!role) return undefined
    const clean = role.toLowerCase().trim()
    const norm = normalizeAgentRole(role)
    return agents.value.find(
      (a) =>
        a.name?.toLowerCase() === clean ||
        normalizeAgentRole(a.role) === norm ||
        a.role?.toLowerCase() === clean,
    )
  }

  function toggleHitlTargetAgent(identifier: string) {
    const agent = findAgent(identifier)
    const targetRole = agent?.role || identifier
    const idx = hitlTargetAgents.value.indexOf(targetRole)
    if (idx !== -1) {
      hitlTargetAgents.value.splice(idx, 1)
    } else {
      hitlTargetAgents.value.push(targetRole)
    }
  }

  function resolveAgentDisplay(role?: string | null) {
    const agent = findAgent(role)
    const isSupervisor =
      role === 'Atenea' ||
      agent?.role === 'supervisor' ||
      agent?.name === 'Atenea' ||
      normalizeAgentRole(role) === 'supervisor'
    const agentRole =
      agent?.role || normalizeAgentRole(role) || (isSupervisor ? 'supervisor' : role || 'supervisor')
    const agentName = agent?.name || (isSupervisor ? 'Atenea' : role || agentRole)
    const colorHex = agent?.color_hex || (isSupervisor ? '#f59e0b' : '#00e5ff')
    return { agentRole, agentName, colorHex }
  }

  function getKnownAgentNames(): string[] {
    const names: string[] = []
    for (const a of agents.value) {
      if (a.role) names.push(a.role)
      if (a.name) names.push(a.name)
    }
    return names
  }

  const tts = createTtsAudioEngine({
    onRoleReadingStart: (normRole) => {
      const ag = findAgent(normRole) || (normRole === 'supervisor' ? findAgent('supervisor') : undefined)
      if (ag && ag.state !== 'ACTIVE') {
        ag.state = 'ACTIVE'
      }
    },
    onRoleReadingEnd: (role, normRole) => {
      const ag = findAgent(role) || (normRole === 'supervisor' ? findAgent('supervisor') : undefined)
      if (ag?.state === 'ACTIVE' && (ag.role !== 'supervisor' || !isDebating.value)) {
        ag.state = 'COMPLETED'
      }
    },
    onAfterStop: () => {
      wakeWord.resetWakeWordSession()
    },
    onGestureUnlock: () => {
      wakeWord.resumeSuspendedContext()
    },
  })

  const wakeWord = useWakeWord({
    isHitlRequired: () => isHitlRequired.value,
    onSilenceCommand: () => tts.stopTts(),
    onHitlDecisionCommand: (decision) => debateStream.submitHitlDecision(decision),
    onHitlRefineCommand: () => tts.stopTts(),
    onToggleHitlTargetAgent: (identifier) => toggleHitlTargetAgent(identifier),
    onWakeWordInterrupt: () => tts.stopTts(),
    onAgentWakeWordSelected: (role) => {
      selectedAgent.value = role
    },
  })

  const debateStream = useDebateStream({
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
    findAgent,
    resolveAgentDisplay,
    getKnownAgentNames,
    recordExecutionTrail,
    isAgentReading: tts.isAgentReading,
    stopTts: tts.stopTts,
    feedTtsStreamingChunk: tts.feedTtsStreamingChunk,
    flushTtsStreamingBuffer: tts.flushTtsStreamingBuffer,
    resetTtsStreamState: tts.resetTtsStreamState,
    clearTtsStreamBuffer: tts.clearTtsStreamBuffer,
    resetWakeWordSession: wakeWord.resetWakeWordSession,
  })

  async function fetchTopology() {
    try {
      topology.value = await configService.getTopology()
    } catch {
      // Ignore network errors or unmocked URLs in testing environments
    }
  }

  async function loadAgents() {
    try {
      const data = await configService.loadAgentsConfig()
      agents.value = data.map((agent) => ({
        role: agent.id,
        name: agent.name,
        description: agent.description,
        color_hex: agent.color_hex,
        uses_rag: agent.uses_rag,
        supports_hitl: agent.supports_hitl,
        can_ingest_documents: agent.can_ingest_documents,
        topology_roles: agent.topology_roles,
        tools: agent.tools,
        turns: 0,
        tokens: 0,
        promptTokens: 0,
        completionTokens: 0,
        state: 'STANDBY',
      }))
      isAgentsLoaded.value = true
      await fetchTopology()
    } catch (error) {
      console.error('Error loading agents:', error)
      agents.value = []
      isAgentsLoaded.value = false
    }
  }

  async function learnSession(
    sessionId?: string | null,
    content?: string,
  ): Promise<{ success: boolean; message: string }> {
    isLearningSession.value = true
    learningStatusMessage.value = null
    try {
      const sid = (sessionId || currentSessionId.value || '').trim()
      if (!sid) {
        throw new Error('No hay sesión activa para guardar en el Vault')
      }
      const data = await debateApiService.learnSession({
        session_id: sid,
        content: content || undefined,
      })
      const rawFile = data.generated_file || data.file
      const fileName = rawFile ? String(rawFile).split('/').pop() : 'nota de arquitectura'
      const msg = `✅ Metis ha asimilado y guardado la síntesis en el Vault: ${fileName}`
      learningStatusMessage.value = msg
      return { success: true, message: msg }
    } catch (err: unknown) {
      const errMsg =
        err instanceof HttpError
          ? formatHttpErrorDetail(err.detail, 'Error al persistir el aprendizaje')
          : err instanceof Error
            ? err.message
            : 'Error inesperado al aprender la sesión'
      learningStatusMessage.value = `❌ Error: ${errMsg}`
      return { success: false, message: errMsg }
    } finally {
      isLearningSession.value = false
    }
  }

  return {
    isConnected,
    isDebating,
    isHitlRequired,
    hitlCheckpoint,
    hitlTargetAgents,
    toggleHitlTargetAgent,
    messages,
    rawEvents,
    draftMessage,
    agents,
    isAgentsLoaded,
    sessionTotalTokens,
    sessionCachedTokens,
    cacheSavingsPercentage,
    isTtsPlaying: tts.isTtsPlaying,
    activeTtsRole: tts.activeTtsRole,
    readingAgentRoles: tts.readingAgentRoles,
    isAgentReading: tts.isAgentReading,
    addReadingAgentRole: tts.addReadingAgentRole,
    removeReadingAgentRole: tts.removeReadingAgentRole,
    clearReadingAgentRoles: tts.clearReadingAgentRoles,
    isVoiceOutputEnabled: tts.isVoiceOutputEnabled,
    isAutoListenEnabled: wakeWord.isAutoListenEnabled,
    isRecording: wakeWord.isRecording,
    isWakeWordTriggered: wakeWord.isWakeWordTriggered,
    selectedAgent,
    selectedAgents,
    globalAudioPlayer: tts.globalAudioPlayer,
    globalAnalyser: tts.globalAnalyser,
    unlockAudioContext: tts.unlockAudioContext,
    playTtsAudioChunk: tts.playTtsAudioChunk,
    stopTts: tts.stopTts,
    currentSessionId,
    clearSession: debateStream.clearSession,
    loadAgents,
    loadDebate: debateStream.loadDebate,
    fetchTopology,
    topology,
    projectName,
    projectDescription,
    executionTrail,
    recordExecutionTrail,
    connect: debateStream.connect,
    disconnect: debateStream.disconnect,
    startDebate: debateStream.startDebate,
    cancelDebate: debateStream.cancelDebate,
    uploadFile,
    handleSupervisorEvent: debateStream.handleSupervisorEvent,
    submitHitlDecision: debateStream.submitHitlDecision,
    startAutoListen: wakeWord.startAutoListen,
    stopAutoListen: wakeWord.stopAutoListen,
    resetWakeWordSession: wakeWord.resetWakeWordSession,
    isLearningSession,
    learningStatusMessage,
    learnSession,
    findAgent,
    normalizeAgentRole,
    streamingMessageId,
    onTtsChunkReady: tts.onTtsChunkReady,
    onTtsStop: tts.onTtsStop,
    cleanAgentMessageContent,
    get ws() {
      return debateStream.rawSocket
    },
  }
})
