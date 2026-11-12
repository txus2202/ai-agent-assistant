import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export type AgentState = 'STANDBY' | 'ACTIVE' | 'COMPLETED' | 'ERROR'
export type HitlDecisionType = 'approve' | 'refine' | 'divert' | 'finish' | 'reject'

export interface Agent {
  role: string
  name: string
  description?: string
  color_hex?: string
  state: AgentState
  tokens?: number
  promptTokens?: number
  completionTokens?: number
  latency?: number
  turns?: number
  startedAt?: number
  uses_rag?: boolean
  supports_hitl?: boolean
  can_ingest_documents?: boolean
  topology_roles?: string[]
  tools?: string[]
}

export interface ChatMessage {
  id?: string
  role: 'user' | 'assistant'
  content: string
  timestamp?: string
  agentRole?: string
  agentName?: string
  colorHex?: string
  isStreaming?: boolean
}

export interface SupervisorEvent {
  type: string
  timestamp?: string
  role?: string | null
  content?: string
  metadata?: {
    checkpoint?: string
    latency_seconds?: number | string
    tokens?: number | string
    prompt_tokens?: number | string
    completion_tokens?: number | string
    total_tokens?: number | string
    cached_tokens?: number | string
    [key: string]: unknown
  }
  [key: string]: unknown
}

export interface DebateSession {
  id?: string
  created_at?: string
  user_request?: string
  status?: string
  events?: SupervisorEvent[]
  [key: string]: unknown
}

export interface DebateTopology {
  project_name?: string
  project_description?: string
  supervisor: string
  interpreters: string[]
  proposers: string[]
  reviewers: string[]
  evaluators: string[]
  implementers: string[]
}

// Resolves WebSocket URL dynamically to support local dev, reverse proxies, and Tailscale (WSS)
export function resolveWsUrl(path: string): string {
  if (import.meta.env.VITE_WS_URL) {
    return import.meta.env.VITE_WS_URL.replace('/ws/debate', path)
  }
  if (typeof window !== 'undefined' && window.location) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    if (window.location.port === '5173' || window.location.port === '4173') {
      return `ws://${window.location.hostname}:8000${path}`
    }
    return `${protocol}//${window.location.host}${path}`
  }
  return `ws://localhost:8000${path}`
}

// Builds a valid 0.1s silent 8-bit mono WAV (Safari rejects malformed/tiny headers)
function buildSilentWavUrl(): string {
  const samples = 800
  const buf = new ArrayBuffer(44 + samples)
  const v = new DataView(buf)
  const str = (o: number, s: string) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.codePointAt(i) ?? 0) }
  str(0, 'RIFF'); v.setUint32(4, 36 + samples, true); str(8, 'WAVE')
  str(12, 'fmt '); v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true)
  v.setUint32(24, 8000, true); v.setUint32(28, 8000, true); v.setUint16(32, 1, true); v.setUint16(34, 8, true)
  str(36, 'data'); v.setUint32(40, samples, true)
  new Uint8Array(buf, 44).fill(128)
  return URL.createObjectURL(new Blob([buf], { type: 'audio/wav' }))
}

export async function uploadFile(file: File): Promise<string> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch('/api/upload', {
    method: 'POST',
    body: formData
  })

  if (!response.ok) {
    throw new Error('Upload failed')
  }

  const data = await response.json()
  return data.path
}

export function normalizeAgentRole(r?: string | null): string {
  if (!r) return ''
  const lower = r.toLowerCase().replaceAll('-', '_').trim()
  if (lower === 'innovator') return 'innovator_architect'
  if (lower === 'atenea') return 'supervisor'
  return lower
}

/**
 * Strips initial agent/role prefixes like "[nl_interpreter] ", "[the_judge] ",
 * and markdown headers like "## Interpretation\n", "## Ícaro\n", "## Sphinx\n".
 */
export function cleanAgentMessageContent(rawContent: string): string {
  if (!rawContent) return ''
  let clean = rawContent.trim()
  const bracketPrefix = /^\[[\w\s.-]+\]\s*/i
  const headerPrefix = /^##\s+(?:Interpretation|Ícaro|Icaro|Hermes|Hestia|Sphinx|the_judge|nl_interpreter|innovator_architect|senior_architect|atenea|supervisor)\s*\n+/i

  let changed = true
  while (changed) {
    changed = false
    if (bracketPrefix.test(clean)) {
      clean = clean.replace(bracketPrefix, '').trim()
      changed = true
    }
    if (headerPrefix.test(clean)) {
      clean = clean.replace(headerPrefix, '').trim()
      changed = true
    }
  }
  return clean
}

export function getToolSpokenFallback(fenceType: string): string {
  if (/mermaid|diagram/.test(fenceType)) {
    return 'He generado el diagrama arquitectónico en pantalla.'
  }
  if (/markdown|md|doc/.test(fenceType)) {
    return 'He generado el documento técnico en pantalla.'
  }
  return 'He generado el código en pantalla.'
}

export function findSentenceSplitIndex(buffer: string): number {
  const terminalMatch = /[.!?\n]/.exec(buffer)
  if (terminalMatch) {
    return terminalMatch.index
  }
  if (buffer.length >= 20) {
    const clauseMatch = /[,:;]/.exec(buffer.slice(20))
    if (clauseMatch) {
      return 20 + clauseMatch.index
    }
  }
  return -1
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
  
  const agents = ref<Agent[]>([])
  const isAgentsLoaded = ref(false)
  const executionTrail = ref<string[]>([])
  const topology = ref<DebateTopology | null>(null)
  const projectName = computed(() => topology.value?.project_name || 'AI AGENT ASSISTANT')
  const projectDescription = computed(() => topology.value?.project_description || 'Asistente de IA Multi-Agente')

  function recordExecutionTrail(name?: string | null) {
    if (!name) return
    const trail = executionTrail.value
    if (trail.at(-1) !== name) {
      executionTrail.value = [...trail, name]
    }
  }

  // Context caching & session token efficiency
  const sessionTotalTokens = ref(0)
  const sessionCachedTokens = ref(0)
  const cacheSavingsPercentage = computed(() => {
    const total = sessionTotalTokens.value + sessionCachedTokens.value
    if (total === 0) return 0
    return Math.min(100, Math.round((sessionCachedTokens.value / total) * 100))
  })

  // TTS State
  const isTtsPlaying = ref(false)
  const activeTtsRole = ref<string | null>(null)
  const readingAgentRoles = ref<string[]>([])
  const isVoiceOutputEnabled = ref(true)
  const globalAudioPlayer = new Audio()

  function isAgentReading(role?: string | null): boolean {
    if (!role || !isVoiceOutputEnabled.value) return false
    const norm = (normalizeAgentRole(role) || role).toLowerCase()
    return readingAgentRoles.value.some(r => {
      const normR = (normalizeAgentRole(r) || r).toLowerCase()
      if (normR === norm) return true
      if ((norm === 'supervisor' || norm === 'atenea') && (normR === 'supervisor' || normR === 'atenea')) return true
      return false
    })
  }

  function addReadingAgentRole(role?: string | null) {
    if (!role || !isVoiceOutputEnabled.value) return
    const norm = normalizeAgentRole(role) || role
    if (!isAgentReading(norm)) {
      readingAgentRoles.value.push(norm)
    }
    const ag = findAgent(norm) || (norm === 'supervisor' ? findAgent('supervisor') : undefined)
    if (ag && ag.state !== 'ACTIVE') {
      ag.state = 'ACTIVE'
    }
  }

  function removeReadingAgentRole(role?: string | null) {
    if (!role) return
    const norm = (normalizeAgentRole(role) || role).toLowerCase()
    readingAgentRoles.value = readingAgentRoles.value.filter(r => {
      const normR = (normalizeAgentRole(r) || r).toLowerCase()
      if (normR === norm) return false
      if ((norm === 'supervisor' || norm === 'atenea') && (normR === 'supervisor' || normR === 'atenea')) return false
      return true
    })
    const ag = findAgent(role) || (norm === 'supervisor' ? findAgent('supervisor') : undefined)
    if (ag?.state === 'ACTIVE' && ag.role !== 'supervisor') {
      ag.state = 'COMPLETED'
    }
    if (activeTtsRole.value) {
      const currentNorm = (normalizeAgentRole(activeTtsRole.value) || activeTtsRole.value).toLowerCase()
      if (currentNorm === norm || ((norm === 'supervisor' || norm === 'atenea') && (currentNorm === 'supervisor' || currentNorm === 'atenea'))) {
        activeTtsRole.value = readingAgentRoles.value[0] || null
      }
    }
  }

  function clearReadingAgentRoles() {
    const wasReading = [...readingAgentRoles.value]
    readingAgentRoles.value = []
    wasReading.forEach(role => {
      const ag = findAgent(role) || (normalizeAgentRole(role) === 'supervisor' ? findAgent('supervisor') : undefined)
      if (ag?.state === 'ACTIVE' && ag.role !== 'supervisor') {
        ag.state = 'COMPLETED'
      }
    })
  }
  
  // Auto-Listen (Wake-Word) State
  // Expose isRecording so WW can be muted
  const isRecording = ref(false)
  const isAutoListenEnabled = ref(false)
  const isWakeWordTriggered = ref(false)
  const selectedAgent = ref<string>('supervisor')
  const selectedAgents = ref<string[]>(['supervisor'])

  // Learning Session State (Metis Vault & Vector persistence)
  const isLearningSession = ref(false)
  const learningStatusMessage = ref<string | null>(null)

  let wakeWordWs: WebSocket | null = null
  let wwAudioContext: AudioContext | null = null
  let wwMicrophone: MediaStreamAudioSourceNode | null = null
  let wwProcessor: AudioWorkletNode | null = null
  let wwStream: MediaStream | null = null

  function resetWakeWordSession() {
    isWakeWordTriggered.value = false
    isRecording.value = false
    if (wakeWordWs?.readyState === WebSocket.OPEN) {
      try {
        wakeWordWs.send(JSON.stringify({ type: 'RESET' }))
      } catch {}
    }
    if (wwAudioContext?.state === 'suspended') {
      wwAudioContext.resume().catch(() => {})
    }
  }
  
  // Need to add crossOrigin to allow Web Audio API to process it
  globalAudioPlayer.crossOrigin = 'anonymous'

  // Web Audio API Context for waveform visualization & TTS playback
  let globalAudioContext: AudioContext | null = null
  const globalAnalyser = ref<AnalyserNode | null>(null)
  let currentTtsSource: AudioBufferSourceNode | null = null

  let silentWavUrl: string | null = null

  function getOrCreateAudioContext(): AudioContext | null {
    if (typeof window === 'undefined') return null
    try {
      if (!globalAudioContext) {
        const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
        if (AudioCtx) {
          globalAudioContext = new AudioCtx()
          const analyser = globalAudioContext.createAnalyser()
          analyser.fftSize = 256
          globalAnalyser.value = analyser
          analyser.connect(globalAudioContext.destination)
        }
      }
      if (globalAudioContext?.state === 'suspended') {
        globalAudioContext.resume().catch(() => {})
      }
      return globalAudioContext
    } catch (e) {
      console.warn("Could not initialize AudioContext", e)
      return null
    }
  }

  function unlockAudioContext() {
    // 1. Try unlocking HTMLMediaElement for fallback compatibility
    try {
      if (!silentWavUrl && typeof window !== 'undefined') silentWavUrl = buildSilentWavUrl()
      if (silentWavUrl && globalAudioPlayer) {
        const unlockUrl = silentWavUrl
        globalAudioPlayer.src = unlockUrl
        globalAudioPlayer.play().then(() => {
          if (globalAudioPlayer.src === unlockUrl) globalAudioPlayer.pause()
        }).catch(() => {})
      }
    } catch {}

    // 2. Create/Resume Web Audio Context and prime with silent buffer (essential for Safari/WebKit)
    try {
      const ctx = getOrCreateAudioContext()
      if (ctx) {
        if (ctx.state === 'suspended') {
          ctx.resume().catch(() => {})
        }
        try {
          const silentBuf = ctx.createBuffer(1, 1, 22050)
          const node = ctx.createBufferSource()
          node.buffer = silentBuf
          node.connect(ctx.destination)
          node.start(0)
        } catch {}
      }
    } catch (e) {
      console.warn("Could not unlock Web Audio Context", e)
    }
  }

  async function playTtsAudioChunk(audioData: ArrayBuffer): Promise<void> {
    if (!isTtsPlaying.value) return
    const ctx = getOrCreateAudioContext()
    if (!ctx?.decodeAudioData) return

    if (ctx.state === 'suspended') {
      await ctx.resume().catch(() => {})
    }

    const copy = audioData.slice(0)
    const audioBuffer = await ctx.decodeAudioData(copy)

    return new Promise((resolve) => {
      if (!isTtsPlaying.value) {
        resolve()
        return
      }

      const source = ctx.createBufferSource()
      source.buffer = audioBuffer

      if (globalAnalyser.value) {
        source.connect(globalAnalyser.value)
      } else {
        source.connect(ctx.destination)
      }

      currentTtsSource = source

      source.onended = () => {
        if (currentTtsSource === source) {
          currentTtsSource = null
        }
        resolve()
      }

      source.start(0)
    })
  }

  function stopTts() {
    isTtsPlaying.value = false
    activeTtsRole.value = null
    ttsStreamBuffer = ''
    clearReadingAgentRoles()
    if (currentTtsSource) {
      try {
        currentTtsSource.stop()
        currentTtsSource.disconnect()
      } catch {}
      currentTtsSource = null
    }
    try {
      globalAudioPlayer.pause()
      globalAudioPlayer.removeAttribute('src')
    } catch {}

    resetWakeWordSession()
  }

  if (typeof window !== 'undefined') {
    const unlockOnGesture = () => {
      unlockAudioContext()
      if (wwAudioContext?.state === 'suspended') {
        wwAudioContext.resume().catch(() => {})
      }
    }
    window.addEventListener('pointerdown', unlockOnGesture, { passive: true })
    window.addEventListener('keydown', unlockOnGesture, { passive: true })
    window.addEventListener('touchstart', unlockOnGesture, { passive: true })
  }

  // Fetch agent topology from backend
  async function loadAgents() {
    try {
      const response = await fetch('/api/config/agents')
      if (!response.ok) throw new Error('Failed to fetch agents config')
      
      const data: Array<{
        id: string
        name: string
        description?: string
        color_hex?: string
        uses_rag?: boolean
        supports_hitl?: boolean
        can_ingest_documents?: boolean
        topology_roles?: string[]
      }> = await response.json()
      agents.value = data.map(agent => ({
        role: agent.id,
        name: agent.name,
        description: agent.description,
        color_hex: agent.color_hex,
        uses_rag: agent.uses_rag,
        supports_hitl: agent.supports_hitl,
        can_ingest_documents: agent.can_ingest_documents,
        topology_roles: agent.topology_roles,
        turns: 0,
        tokens: 0,
        promptTokens: 0,
        completionTokens: 0,
        state: 'STANDBY'
      }))
      isAgentsLoaded.value = true
      await fetchTopology()
    } catch (error) {
      console.error('Error loading agents:', error)
      agents.value = []
      isAgentsLoaded.value = false
    }
  }

  async function fetchTopology() {
    try {
      const endpoint = typeof window !== 'undefined' && window.location?.origin
        ? `${window.location.origin}/api/config/topology`
        : '/api/config/topology'
      const response = await fetch(endpoint)
      if (response.ok) {
        topology.value = await response.json()
      }
    } catch {
      // Ignore network errors or unmocked URLs in testing environments
    }
  }


  let ws: WebSocket | null = null
  let reconnectAttempts = 0
  let reconnectTimeout: ReturnType<typeof setTimeout> | null = null
  let shouldReconnect = true

  function connect() {
    shouldReconnect = true
    const wsUrl = resolveWsUrl('/ws/debate')
    
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      return
    }

    ws = new WebSocket(wsUrl)
    
    ws.onopen = () => {
      console.log('[WS] Connected to', wsUrl)
      isConnected.value = true
      reconnectAttempts = 0
    }
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        // Add timestamp to raw event if not present
        if (!data.timestamp) {
          data.timestamp = new Date().toISOString()
        }
        rawEvents.value.push(data)
        handleSupervisorEvent(data)
      } catch {
        console.error('[WS] Failed to parse message', event.data)
      }
    }
    
    ws.onclose = () => {
      console.log('[WS] Disconnected')
      isConnected.value = false
      if (isDebating.value) {
        handleError({
          type: 'error',
          content: 'Conexión interrumpida con el servidor de agentes.'
        })
      }
      ws = null
      if (shouldReconnect) {
        attemptReconnect()
      }
    }
    
    ws.onerror = (error) => {
      console.error('[WS] Error', error)
      if (isDebating.value) {
        handleError({
          type: 'error',
          content: 'Error de comunicación WebSocket con el servidor.'
        })
      }
    }
  }

  function disconnect() {
    shouldReconnect = false
    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout)
      reconnectTimeout = null
    }
    reconnectAttempts = 0
    if (ws) {
      ws.onclose = null
      ws.close()
      ws = null
    }
    isConnected.value = false
  }

  function attemptReconnect() {
    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout)
    }
    
    // Exponential backoff (max 10s)
    const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 10000)
    console.log(`[WS] Attempting to reconnect in ${delay}ms...`)
    
    reconnectTimeout = setTimeout(() => {
      reconnectAttempts++
      connect()
    }, delay)
  }

  function clearSession() {
    messages.value = []
    rawEvents.value = []
    currentSessionId.value = null
    sessionTotalTokens.value = 0
    sessionCachedTokens.value = 0
    isHitlRequired.value = false
    hitlCheckpoint.value = null
    hitlTargetAgents.value = []
    isDebating.value = false
    executionTrail.value = []
    agents.value.forEach(a => {
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
      currentSessionId.value = debate.id
    }
    
    // Check if any event is of type user_message
    const hasUserMessageEvents = debate.events && Array.isArray(debate.events) && debate.events.some(e => e.type === 'user_message')
    if (!hasUserMessageEvents && debate.user_request) {
      messages.value.push({
        id: crypto.randomUUID(),
        role: 'user',
        content: debate.user_request,
        timestamp: new Date().toISOString()
      } as ChatMessage)
    }
    
    if (debate.events && Array.isArray(debate.events)) {
      debate.events.forEach((event: SupervisorEvent) => {
        rawEvents.value.push(event)
        handleSupervisorEvent(event)
      })
    }
    
    isDebating.value = debate.status === 'running'
  }

  function startDebate(userRequest: string, targetAgent: string | string[] = 'supervisor', attachmentUrl: string | string[] | null = null) {
    stopTts() // Interrupt any ongoing TTS

    if (!isConnected.value || !ws) {
      messages.value.push({ role: 'assistant', content: 'Error: Cannot start debate, disconnected from server. Trying to reconnect...' })
      connect()
      return
    }
    
    // Initialize session_id if starting a fresh session
    if (!currentSessionId.value) {
      currentSessionId.value = crypto.randomUUID()
      sessionTotalTokens.value = 0
      sessionCachedTokens.value = 0
    }

    // Resolve target agent(s)
    let targetAgentsList: string[]
    if (Array.isArray(targetAgent)) {
      targetAgentsList = targetAgent.length > 0 ? targetAgent : ['supervisor']
    } else {
      targetAgentsList = [targetAgent || 'supervisor']
    }
    const primaryTarget = targetAgentsList[0] || 'supervisor'

    // Reset agent states to STANDBY for the new turn
    agents.value.forEach(a => a.state = 'STANDBY')
    targetAgentsList.forEach(role => {
      const startingAgent = findAgent(role) || (normalizeAgentRole(role) === 'supervisor' ? findAgent('supervisor') : undefined)
      if (startingAgent) {
        startingAgent.state = 'ACTIVE'
        startingAgent.startedAt = Date.now()
        startingAgent.turns = (startingAgent.turns || 0) + 1
      }
    })

    // Register Atenea triage tokens immediately as they are consumed for intent classification
    const sup = findAgent('supervisor')
    if (sup && (targetAgentsList.includes('supervisor') || targetAgentsList.includes('Atenea') || targetAgentsList.length === 0)) {
      const words = userRequest.trim().split(/\s+/).filter(Boolean).length
      const triagePromptTokens = Math.max(30, Math.round(words * 1.35) + 140)
      const triageCompletionTokens = 25
      sup.promptTokens = (sup.promptTokens || 0) + triagePromptTokens
      sup.completionTokens = (sup.completionTokens || 0) + triageCompletionTokens
      sup.tokens = (sup.tokens || 0) + triagePromptTokens + triageCompletionTokens
      sessionTotalTokens.value += triagePromptTokens + triageCompletionTokens
    }
    executionTrail.value = ['Atenea']
    
    // Capture session chat history before adding the new user message
    const history = messages.value.slice(-10).map(m => ({
      role: m.role,
      content: m.content,
      agent: m.agentName || m.agentRole
    }))
    
    isDebating.value = true
    messages.value.push({
      id: crypto.randomUUID(),
      role: 'user',
      content: userRequest,
      timestamp: new Date().toISOString()
    })
    
    let attachments: string[] = []
    if (Array.isArray(attachmentUrl)) {
      attachments = attachmentUrl
    } else if (attachmentUrl) {
      attachments = [attachmentUrl]
    }

    const payload: Record<string, unknown> = {
      type: 'start',
      session_id: currentSessionId.value,
      user_request: userRequest,
      target_agent: primaryTarget,
      attachments,
      history
    }
    if (Array.isArray(targetAgent)) {
      payload.target_agents = targetAgentsList
    }
    ws.send(JSON.stringify(payload))
  }

  function cancelDebate() {
    if (!isDebating.value) return

    stopTts()

    agents.value.forEach(a => {
      if (a.state === 'ACTIVE') {
        if (a.startedAt && !a.latency) {
          a.latency = Number(((Date.now() - a.startedAt) / 1000).toFixed(2))
        }
        a.state = 'STANDBY'
      }
    })

    isDebating.value = false
    isHitlRequired.value = false
    hitlCheckpoint.value = null
    hitlTargetAgents.value = []

    if (ws) {
      try {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'cancel' }))
        }
      } catch (e) {
        console.warn('Failed to send cancel over WebSocket:', e)
      }
      disconnect()
      connect()
    }

    messages.value.push({
      id: crypto.randomUUID(),
      role: 'assistant',
      agentName: projectName.value,
      agentRole: 'supervisor',
      content: '⚠️ Deliberación cancelada por el usuario. Puedes reformular tu consulta o iniciar una nueva cuando desees.',
      timestamp: new Date().toISOString()
    })
  }

  function findAgent(role?: string | null): Agent | undefined {
    if (!role) return undefined
    const clean = role.toLowerCase().trim()
    const norm = normalizeAgentRole(role)
    return agents.value.find(a => 
      a.name?.toLowerCase() === clean || 
      normalizeAgentRole(a.role) === norm ||
      a.role?.toLowerCase() === clean
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
    const isSupervisor = role === 'Atenea' || agent?.role === 'supervisor' || agent?.name === 'Atenea' || normalizeAgentRole(role) === 'supervisor'
    const agentRole = agent?.role || normalizeAgentRole(role) || (isSupervisor ? 'supervisor' : role || 'supervisor')
    const agentName = agent?.name || (isSupervisor ? 'Atenea' : role || agentRole)
    const colorHex = agent?.color_hex || (isSupervisor ? '#f59e0b' : '#00e5ff')
    return { agentRole, agentName, colorHex }
  }

  function pushAgentMessage(content: string, role?: string | null) {
    const { agentRole, agentName, colorHex } = resolveAgentDisplay(role)
    const cleanContent = cleanAgentMessageContent(content)
    messages.value.push({
      role: 'assistant',
      content: cleanContent,
      agentRole,
      agentName,
      colorHex
    })
  }

  function handleHitlRequired(event: SupervisorEvent) {
    isHitlRequired.value = true
    const checkpoint = event.metadata?.checkpoint
    hitlCheckpoint.value = checkpoint || null
    const checkpointAgent = checkpoint?.startsWith('after_') ? checkpoint.replace('after_', '') : undefined
    const metadataAgent = typeof event.metadata?.agent === 'string' ? event.metadata.agent : undefined
    const role = metadataAgent || event.role || checkpointAgent || 'Atenea'
    pushAgentMessage(event.content || 'HITL Required', role)
  }

  function handleAgentStarted(event: SupervisorEvent) {
    const agent = findAgent(event.role) || (normalizeAgentRole(event.role) === 'supervisor' ? findAgent('supervisor') : undefined)
    if (!agent) return

    // If a delegated agent starts, transition supervisor to standby (her presence remains in the orb and topology)
    if (agent.role !== 'supervisor') {
      const sup = findAgent('supervisor')
      if (sup?.state === 'ACTIVE') {
        if (sup.startedAt) {
          sup.latency = Number(((Date.now() - sup.startedAt) / 1000).toFixed(2))
        }
        sup.state = 'STANDBY'
      }
    }

    agent.state = 'ACTIVE'
    agent.turns = (agent.turns || 0) + 1
    agent.startedAt = Date.now()
    recordExecutionTrail(agent.name)
  }

  function updateAgentLatency(agent: Agent, event: SupervisorEvent) {
    if (event.metadata?.latency_seconds) {
      agent.latency = Number(event.metadata.latency_seconds)
    } else if (agent.startedAt) {
      agent.latency = Number(((Date.now() - agent.startedAt) / 1000).toFixed(2))
    }
  }

  function updateAgentTokens(agent: Agent, event: SupervisorEvent): number {
    let pTokens = 0
    let cTokens = 0
    if (event.metadata?.prompt_tokens) {
      pTokens = Number.parseInt(String(event.metadata.prompt_tokens), 10) || 0
      if (pTokens > 0) {
        agent.promptTokens = (agent.promptTokens || 0) + pTokens
      }
    }
    if (event.metadata?.completion_tokens) {
      cTokens = Number.parseInt(String(event.metadata.completion_tokens), 10) || 0
      if (cTokens > 0) {
        agent.completionTokens = (agent.completionTokens || 0) + cTokens
      }
    }

    if (event.metadata?.tokens || event.metadata?.total_tokens) {
      const tokens = Number.parseInt(String(event.metadata.total_tokens || event.metadata.tokens), 10)
      agent.tokens = (agent.tokens || 0) + tokens
      if (!pTokens && !cTokens) {
        const estIn = Math.max(15, Math.round(tokens * 0.6))
        const estOut = Math.max(10, tokens - estIn)
        agent.promptTokens = (agent.promptTokens || 0) + estIn
        agent.completionTokens = (agent.completionTokens || 0) + estOut
      } else if (!pTokens && cTokens > 0) {
        const estIn = Math.max(15, Math.round(cTokens * 1.2))
        agent.promptTokens = (agent.promptTokens || 0) + estIn
        agent.tokens = (agent.tokens || 0) + estIn
      }
      return tokens
    }
    if (event.content) {
      const words = event.content.trim().split(/\s+/).filter(Boolean).length
      const outTokens = Math.max(12, Math.round(words * 1.35))
      const inTokens = Math.max(25, Math.round(outTokens * 1.4))
      agent.tokens = (agent.tokens || 0) + outTokens + inTokens
      agent.promptTokens = (agent.promptTokens || 0) + inTokens
      agent.completionTokens = (agent.completionTokens || 0) + outTokens
      return outTokens + inTokens
    }
    return 0
  }

  function updateCachedTokens(event: SupervisorEvent, estTokens: number) {
    if (event.metadata?.cached_tokens) {
      sessionCachedTokens.value += Number.parseInt(String(event.metadata.cached_tokens), 10)
      return
    }
    if (estTokens > 0) {
      const completedCount = agents.value.filter(a => a.state === 'COMPLETED').length
      if (completedCount > 1) {
        sessionCachedTokens.value += Math.round(estTokens * 0.65)
      }
    }
  }

  function handleAgentCompleted(event: SupervisorEvent) {
    const agent = findAgent(event.role) || (normalizeAgentRole(event.role) === 'supervisor' ? findAgent('supervisor') : undefined)
    if (!agent) return

    if (!isAgentReading(agent.role)) {
      agent.state = 'COMPLETED'
    }
    updateAgentLatency(agent, event)
    const estTokens = updateAgentTokens(agent, event)
    updateCachedTokens(event, estTokens)
    sessionTotalTokens.value += estTokens
  }

  // Streaming TTS & chunk accumulation for real-time speech synthesis
  const streamingMessageId = ref<string | null>(null)
  let ttsStreamBuffer = ''
  let isInsideCodeFence = false
  let codeFenceType = ''
  let hasSpokenInCurrentMessage = false
  const ttsChunkCallbacks: Array<(chunk: string, role?: string) => void> = []

  function onTtsChunkReady(callback: (chunk: string, role?: string) => void) {
    ttsChunkCallbacks.push(callback)
  }

  function emitTtsText(text: string, role?: string) {
    if (!text) return
    for (const cb of ttsChunkCallbacks) {
      cb(text, role)
    }
    hasSpokenInCurrentMessage = true
  }

  function handleOpenFenceInStream(fenceIdx: number, role?: string) {
    const textBefore = ttsStreamBuffer.slice(0, fenceIdx).trim()
    if (textBefore) {
      emitTtsText(textBefore, role)
    }
    isInsideCodeFence = true
    ttsStreamBuffer = ttsStreamBuffer.slice(fenceIdx + 3)
    const newlineIdx = ttsStreamBuffer.indexOf('\n')
    if (newlineIdx !== -1) {
      codeFenceType = ttsStreamBuffer.slice(0, newlineIdx).trim().toLowerCase()
      ttsStreamBuffer = ttsStreamBuffer.slice(newlineIdx + 1)
    }
  }

  function processOutsideFenceChunk(role?: string): boolean {
    const fenceIdx = ttsStreamBuffer.indexOf('```')
    if (fenceIdx !== -1) {
      handleOpenFenceInStream(fenceIdx, role)
      return true
    }

    const splitIdx = findSentenceSplitIndex(ttsStreamBuffer)
    if (splitIdx !== -1) {
      const sentence = ttsStreamBuffer.slice(0, splitIdx + 1).trim()
      ttsStreamBuffer = ttsStreamBuffer.slice(splitIdx + 1)
      emitTtsText(sentence, role)
      return true
    }
    return false
  }

  function processInsideFenceChunk(role?: string): boolean {
    const closeFenceIdx = ttsStreamBuffer.indexOf('```')
    if (closeFenceIdx !== -1) {
      isInsideCodeFence = false
      ttsStreamBuffer = ttsStreamBuffer.slice(closeFenceIdx + 3)
      if (!hasSpokenInCurrentMessage) {
        emitTtsText(getToolSpokenFallback(codeFenceType), role)
      }
      codeFenceType = ''
      return true
    }

    if (ttsStreamBuffer.length > 10) {
      ttsStreamBuffer = ttsStreamBuffer.slice(-4)
    }
    return false
  }

  function feedTtsStreamingChunk(chunk: string, role?: string) {
    if (!isVoiceOutputEnabled.value) return
    ttsStreamBuffer += chunk

    while (ttsStreamBuffer.length > 0) {
      const advanced = !isInsideCodeFence
        ? processOutsideFenceChunk(role)
        : processInsideFenceChunk(role)

      if (!advanced) {
        break
      }
    }
  }

  function flushTtsStreamingBuffer(role?: string) {
    if (!isVoiceOutputEnabled.value) return
    if (!isInsideCodeFence) {
      const remaining = ttsStreamBuffer.trim()
      ttsStreamBuffer = ''
      emitTtsText(remaining, role)
    } else {
      if (!hasSpokenInCurrentMessage) {
        emitTtsText(getToolSpokenFallback(codeFenceType), role)
      }
      ttsStreamBuffer = ''
      isInsideCodeFence = false
      codeFenceType = ''
    }
  }

  function handleStreamChunk(event: SupervisorEvent) {
    const { agentRole, agentName, colorHex } = resolveAgentDisplay(event.role)
    const chunk = event.content || ''

    let targetMsg = streamingMessageId.value ? messages.value.find(m => m.id === streamingMessageId.value) : null

    if (!targetMsg) {
      const newId = crypto.randomUUID()
      streamingMessageId.value = newId
      ttsStreamBuffer = ''
      isInsideCodeFence = false
      codeFenceType = ''
      hasSpokenInCurrentMessage = false
      targetMsg = {
        id: newId,
        role: 'assistant',
        content: chunk,
        agentRole,
        agentName,
        colorHex,
        isStreaming: true,
      }
      messages.value.push(targetMsg)
    } else {
      targetMsg.content += chunk
    }

    // Ensure the streaming agent's card is marked active and increment completion tokens progressively
    const targetRole = agentRole || event.role || 'supervisor'
    const streamingAgent = findAgent(targetRole)
    if (streamingAgent) {
      if (streamingAgent.state !== 'ACTIVE') {
        streamingAgent.state = 'ACTIVE'
      }
      const chunkTokens = Math.max(1, Math.round(chunk.length / 4))
      streamingAgent.completionTokens = (streamingAgent.completionTokens || 0) + chunkTokens
      streamingAgent.tokens = (streamingAgent.tokens || 0) + chunkTokens
      sessionTotalTokens.value += chunkTokens
    }

    feedTtsStreamingChunk(chunk, agentRole || event.role || undefined)
  }

  function handleDone(event: SupervisorEvent) {
    isDebating.value = false
    resetWakeWordSession()
    
    // Mark any remaining active agents as COMPLETED unless they are currently reading TTS
    agents.value.forEach(a => {
      if (a.state === 'ACTIVE' && !isAgentReading(a.role)) {
        a.state = 'COMPLETED'
      }
    })

    // Update Atenea (supervisor) observability metrics from the DONE consolidation event
    const sup = findAgent(event.role) || (normalizeAgentRole(event.role) === 'supervisor' ? findAgent('supervisor') : undefined) || findAgent('supervisor')
    if (sup) {
      if (event.metadata) {
        updateAgentLatency(sup, event)
        const estTokens = updateAgentTokens(sup, event)
        updateCachedTokens(event, estTokens)
        sessionTotalTokens.value += estTokens
      } else if (event.content) {
        const words = event.content.trim().split(/\s+/).filter(Boolean).length
        const outTokens = Math.max(12, Math.round(words * 1.35))
        const inTokens = Math.max(25, Math.round(outTokens * 1.4))
        sup.tokens = (sup.tokens || 0) + outTokens + inTokens
        sup.promptTokens = (sup.promptTokens || 0) + inTokens
        sup.completionTokens = (sup.completionTokens || 0) + outTokens
        sessionTotalTokens.value += outTokens + inTokens
      }
      sup.turns = Math.max(1, (sup.turns || 0) + 1)
      if (!isAgentReading(sup.role)) {
        sup.state = 'COMPLETED'
      }
    }
    
    if (streamingMessageId.value) {
      const targetMsg = messages.value.find(m => m.id === streamingMessageId.value)
      if (targetMsg) {
        targetMsg.isStreaming = false
        if (event.content) {
          targetMsg.content = cleanAgentMessageContent(event.content)
        }
      }
      streamingMessageId.value = null
      flushTtsStreamingBuffer(event.role || undefined)
    } else if (event.content?.trim()) {
      pushAgentMessage(event.content, event.role)
    }
    recordExecutionTrail('Atenea')
  }

  function handleError(event: SupervisorEvent) {
    isDebating.value = false
    streamingMessageId.value = null
    ttsStreamBuffer = ''
    stopTts()
    resetWakeWordSession()

    // Stop timers and return active agents to inactive STANDBY state
    agents.value.forEach(a => {
      if (a.state === 'ACTIVE') {
        if (a.startedAt) {
          a.latency = Number(((Date.now() - a.startedAt) / 1000).toFixed(2))
          a.startedAt = undefined
        }
        a.state = 'STANDBY'
      }
    })

    const errorContent = `Error: ${event.content}`
    const lastMsg = messages.value.at(-1)
    if (lastMsg?.role === 'assistant' && (lastMsg.content === errorContent || lastMsg.content === event.content)) {
      return
    }

    const { agentRole, agentName, colorHex } = resolveAgentDisplay(event.role || 'supervisor')
    messages.value.push({
      role: 'assistant',
      content: errorContent,
      agentRole,
      agentName,
      colorHex
    })
  }

  function handleMessage(event: SupervisorEvent) {
    pushAgentMessage(event.content || '', event.role)
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
        handleMessage(event)
        break
      case 'user_message':
        messages.value.push({
          id: crypto.randomUUID(),
          role: 'user',
          content: event.content || '',
          timestamp: new Date().toISOString()
        })
        break
    }
  }

  function submitHitlDecision(
    decision: HitlDecisionType,
    feedback?: string,
    targetAgents?: string[]
  ) {
    stopTts()
    isHitlRequired.value = false
    if (hitlCheckpoint.value) {
      const checkpointAgent = hitlCheckpoint.value.startsWith('after_')
        ? hitlCheckpoint.value.replace('after_', '')
        : hitlCheckpoint.value
      const ag = findAgent(checkpointAgent)
      if (ag && ag.state === 'ACTIVE' && ag.role !== 'supervisor') {
        ag.state = 'COMPLETED'
      }
    }
    hitlCheckpoint.value = null
    resetWakeWordSession()


    const effectiveTargets = targetAgents ?? [...hitlTargetAgents.value]
    hitlTargetAgents.value = []
    
    if ((decision === 'refine' || decision === 'divert') && feedback?.trim()) {
      messages.value.push({
        id: crypto.randomUUID(),
        role: 'user',
        content: feedback.trim(),
        timestamp: new Date().toISOString()
      })
    } else if (decision === 'finish') {
      messages.value.push({
        id: crypto.randomUUID(),
        role: 'user',
        content: 'Finalizar debate anticipadamente y consolidar dictamen.',
        timestamp: new Date().toISOString()
      })
    }

    if (ws?.readyState === WebSocket.OPEN) {
      const payload: {
        type: string
        decision: HitlDecisionType
        feedback: string
        target_agents?: string[]
      } = {
        type: 'hitl_response',
        decision,
        feedback: feedback || ''
      }
      if (effectiveTargets?.length) {
        payload.target_agents = effectiveTargets
      }
      ws.send(JSON.stringify(payload))
    }
  }

  // WebSocket connection is initiated explicitly after user authentication in App.vue

  function startAutoListen() {
    if (isAutoListenEnabled.value) return
    isAutoListenEnabled.value = true
    isWakeWordTriggered.value = false

    // Create AudioContext immediately on user click to avoid browser suspension
    wwAudioContext = new AudioContext({ sampleRate: 16000 })
    
    const wsUrl = resolveWsUrl('/ws/audio/wake-word')
    
    wakeWordWs = new WebSocket(wsUrl)
    wakeWordWs.binaryType = 'arraybuffer'

    wakeWordWs.onopen = async () => {
      console.log('[WW] Connected to wake-word stream')
      try {
        wwStream = await navigator.mediaDevices.getUserMedia({ audio: true })
        
        // Resume if suspended
        if (wwAudioContext?.state === 'suspended') {
          await wwAudioContext.resume()
        }
        wwMicrophone = wwAudioContext!.createMediaStreamSource(wwStream)
        
        // Use an AudioWorklet (inline module) to get raw PCM in 4096-sample chunks
        const workletCode = `
          class PcmCaptureProcessor extends AudioWorkletProcessor {
            constructor() {
              super()
              this.buffer = new Float32Array(4096)
              this.offset = 0
            }
            process(inputs) {
              const input = inputs[0] && inputs[0][0]
              if (!input) return true
              for (let i = 0; i < input.length; i++) {
                this.buffer[this.offset++] = input[i]
                if (this.offset === this.buffer.length) {
                  this.port.postMessage(this.buffer.slice())
                  this.offset = 0
                }
              }
              return true
            }
          }
          registerProcessor('pcm-capture-processor', PcmCaptureProcessor)
        `
        const workletUrl = URL.createObjectURL(
          new Blob([workletCode], { type: 'application/javascript' }),
        )
        try {
          await wwAudioContext!.audioWorklet.addModule(workletUrl)
        } finally {
          URL.revokeObjectURL(workletUrl)
        }

        wwProcessor = new AudioWorkletNode(wwAudioContext!, 'pcm-capture-processor')
        wwMicrophone.connect(wwProcessor)

        // Connect through a zero-gain node to destination to keep the AudioWorklet clock running continuously
        try {
          const silentGain = wwAudioContext!.createGain()
          silentGain.gain.value = 0
          wwProcessor.connect(silentGain)
          silentGain.connect(wwAudioContext!.destination)
        } catch {}

        wwProcessor.port.onmessage = (e: MessageEvent<Float32Array>) => {
          if (wakeWordWs?.readyState !== WebSocket.OPEN) return
          
          // Do not listen for wake word if we are currently recording
          if (isRecording.value) return

          // Auto-resume AudioContext if suspended
          if (wwAudioContext?.state === 'suspended') {
            wwAudioContext.resume().catch(() => {})
          }

          const inputData = e.data
          // Convert Float32 to Int16
          const pcm16 = new Int16Array(inputData.length)
          for (let i = 0; i < inputData.length; i++) {
            const s = Math.max(-1, Math.min(1, inputData[i] || 0))
            pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF
          }
          wakeWordWs.send(pcm16.buffer)
        }
      } catch (e) {
        console.error('[WW] Error accessing microphone for auto-listen', e)
        stopAutoListen()
      }
    }

    function handleHitlVoiceCommand(command: string) {
      if (!isHitlRequired.value) return

      if (command === 'refine') {
        stopTts()
        isWakeWordTriggered.value = true
        setTimeout(() => {
          isWakeWordTriggered.value = false
        }, 1000)
        return
      }

      const decisionMap: Record<string, HitlDecisionType> = {
        approve: 'approve',
        reject: 'reject',
        finish: 'finish',
        divert: 'divert',
      }
      const decision = decisionMap[command]
      if (decision) {
        submitHitlDecision(decision)
      }
    }

    function handleWakeWordDetected(data: { agent_role?: string; display_name?: string }) {
      console.log('[WW] Wake word detected for agent:', data.agent_role || 'supervisor')
      if (isHitlRequired.value) {
        const targetIdentifier = data.agent_role || data.display_name
        if (targetIdentifier) {
          toggleHitlTargetAgent(targetIdentifier)
        }
        return
      }

      stopTts() // Interrupt any ongoing TTS
      if (data.agent_role) {
        selectedAgent.value = data.agent_role
      }
      isWakeWordTriggered.value = true

      setTimeout(() => {
        isWakeWordTriggered.value = false
      }, 1000)
    }

    wakeWordWs.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'SILENCE_VOICE_COMMAND') {
          console.log('[WW] Silence voice command received')
          stopTts()
          return
        }
        if (data.type === 'HITL_VOICE_COMMAND') {
          console.log('[WW] HITL Voice command received:', data.command)
          handleHitlVoiceCommand(data.command)
          return
        }
        if (data.type === 'WAKE_WORD_DETECTED') {
          handleWakeWordDetected(data)
        }
      } catch {}
    }

    wakeWordWs.onclose = () => {
      console.log('[WW] Disconnected from wake-word stream')
      stopAutoListen()
    }
  }

  function stopAutoListen() {
    isAutoListenEnabled.value = false
    isWakeWordTriggered.value = false
    
    if (wakeWordWs) {
      wakeWordWs.close()
      wakeWordWs = null
    }
    if (wwProcessor) {
      wwProcessor.disconnect()
      wwProcessor = null
    }
    if (wwMicrophone) {
      wwMicrophone.disconnect()
      wwMicrophone = null
    }
    if (wwAudioContext) {
      wwAudioContext.close().catch(() => {})
      wwAudioContext = null
    }
    if (wwStream) {
      wwStream.getTracks().forEach(t => t.stop())
      wwStream = null
    }
  }

  async function learnSession(sessionId?: string | null, content?: string): Promise<{ success: boolean; message: string }> {
    isLearningSession.value = true
    learningStatusMessage.value = null
    try {
      const sid = sessionId || currentSessionId.value
      const response = await fetch('/api/learning/session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sid || undefined,
          content: content || undefined,
        }),
      })
      if (!response.ok) {
        const err = await response.json().catch(() => ({}))
        throw new Error(err.detail || 'Error al persistir el aprendizaje')
      }
      const data = await response.json()
      const fileName = data.generated_file ? data.generated_file.split('/').pop() : 'nota de arquitectura'
      const msg = `✅ Metis ha asimilado y guardado la síntesis en el Vault: ${fileName}`
      learningStatusMessage.value = msg
      return { success: true, message: msg }
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : 'Error inesperado al aprender la sesión'
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
    isTtsPlaying,
    activeTtsRole,
    readingAgentRoles,
    isAgentReading,
    addReadingAgentRole,
    removeReadingAgentRole,
    clearReadingAgentRoles,
    isVoiceOutputEnabled,
    isAutoListenEnabled,
    isRecording,
    isWakeWordTriggered,
    selectedAgent,
    selectedAgents,
    globalAudioPlayer,
    globalAnalyser,
    unlockAudioContext,
    playTtsAudioChunk,
    stopTts,
    currentSessionId,
    clearSession,
    loadAgents,
    loadDebate,
    fetchTopology,
    topology,
    projectName,
    projectDescription,
    executionTrail,
    recordExecutionTrail,
    connect,
    disconnect,
    startDebate,
    cancelDebate,
    uploadFile,
    handleSupervisorEvent,
    submitHitlDecision,
    startAutoListen,
    stopAutoListen,
    resetWakeWordSession,
    isLearningSession,
    learningStatusMessage,
    learnSession,
    findAgent,
    normalizeAgentRole,
    streamingMessageId,
    onTtsChunkReady,
    cleanAgentMessageContent,
    get ws() { return ws } // Getter for testing purposes
  }
})
