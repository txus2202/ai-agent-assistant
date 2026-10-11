import { defineStore } from 'pinia'
import { ref } from 'vue'

export type AgentState = 'STANDBY' | 'ACTIVE' | 'COMPLETED'

export interface Agent {
  role: string
  name: string
  state: AgentState
}

export interface ChatMessage {
  id?: string
  role: 'user' | 'assistant'
  content: string
  timestamp?: string
  agentName?: string
}

export interface SupervisorEvent {
  type: string
  timestamp?: string
  role?: string | null
  content?: string
  metadata?: {
    checkpoint?: string
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

export const useDebateStore = defineStore('debate', () => {
  const isConnected = ref(false)
  const isDebating = ref(false)
  const isHitlRequired = ref(false)
  const hitlCheckpoint = ref<string | null>(null)
  const messages = ref<ChatMessage[]>([])
  const rawEvents = ref<SupervisorEvent[]>([])
  const draftMessage = ref('')
  
  const agents = ref<Agent[]>([])
  const isAgentsLoaded = ref(false)

  // TTS State
  const isTtsPlaying = ref(false)
  const activeTtsRole = ref<string | null>(null)
  const isVoiceOutputEnabled = ref(true)
  const globalAudioPlayer = new Audio()
  
  // Auto-Listen (Wake-Word) State
  // Expose isRecording so WW can be muted
  const isRecording = ref(false)
  const isAutoListenEnabled = ref(false)
  const isWakeWordTriggered = ref(false)
  
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
  }

  if (typeof window !== 'undefined') {
    const unlockOnGesture = () => {
      unlockAudioContext()
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
      
      const data: Array<{ id: string, name: string }> = await response.json()
      agents.value = data.map(agent => ({
        role: agent.id,
        name: agent.name,
        state: 'STANDBY'
      }))
      isAgentsLoaded.value = true
    } catch (error) {
      console.error('Error loading agents:', error)
      // Fallback for dev if backend isn't running
      agents.value = [
        { role: 'nl_interpreter', name: 'Nl Interpreter', state: 'STANDBY' },
        { role: 'innovator_architect', name: 'Innovator Architect', state: 'STANDBY' },
        { role: 'senior_architect', name: 'Senior Architect', state: 'STANDBY' },
        { role: 'the_judge', name: 'The Judge', state: 'STANDBY' },
        { role: 'diagrammer', name: 'Diagrammer', state: 'STANDBY' },
        { role: 'devops_secops', name: 'Devops Secops', state: 'STANDBY' }
      ]
      isAgentsLoaded.value = true
    }
  }

  let ws: WebSocket | null = null
  let reconnectAttempts = 0
  let reconnectTimeout: ReturnType<typeof setTimeout> | null = null

  function connect() {
    const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/debate'
    
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
      ws = null
      attemptReconnect()
    }
    
    ws.onerror = (error) => {
      console.error('[WS] Error', error)
      // onclose will be triggered automatically
    }
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

  function loadDebate(debate: DebateSession) {
    messages.value = []
    rawEvents.value = []
    isHitlRequired.value = false
    hitlCheckpoint.value = null
    
    // Reset agent states to STANDBY
    agents.value.forEach(a => a.state = 'STANDBY')
    
    if (debate.user_request) {
      messages.value.push({
        role: 'user',
        content: debate.user_request,
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

  function startDebate(userRequest: string, targetAgent: string = 'supervisor', attachmentUrl: string | null = null) {
    stopTts() // Interrupt any ongoing TTS

    if (!isConnected.value || !ws) {
      messages.value.push({ role: 'assistant', content: 'Error: Cannot start debate, disconnected from server. Trying to reconnect...' })
      connect()
      return
    }
    
    // Reset agent states to STANDBY for the new debate
    agents.value.forEach(a => a.state = 'STANDBY')
    
    isDebating.value = true
    messages.value.push({
      id: crypto.randomUUID(),
      role: 'user',
      content: userRequest,
      timestamp: new Date().toISOString()
    })
    
    const payload = {
      type: 'start',
      user_request: userRequest,
      target_agent: targetAgent,
      attachments: attachmentUrl ? [attachmentUrl] : []
    }
    ws.send(JSON.stringify(payload))
  }

  function handleSupervisorEvent(event: SupervisorEvent) {
    if (event.type === 'hitl_required') {
      isHitlRequired.value = true
      hitlCheckpoint.value = event.metadata?.checkpoint || null
      messages.value.push({ role: 'assistant', content: event.content || 'HITL Required' })
    } else if (event.type === 'agent_started') {
      const agent = agents.value.find(a => a.role === event.role)
      if (agent) agent.state = 'ACTIVE'
    } else if (event.type === 'agent_completed') {
      const agent = agents.value.find(a => a.role === event.role)
      if (agent) agent.state = 'COMPLETED'
    } else if (event.type === 'done') {
      isDebating.value = false
      const prefix = event.role ? `[${event.role}] ` : ''
      messages.value.push({ role: 'assistant', content: prefix + (event.content || 'Debate finished.') })
    } else if (event.type === 'error') {
      isDebating.value = false
      messages.value.push({ role: 'assistant', content: `Error: ${event.content}` })
    } else if (event.type === 'message') {
      messages.value.push({ role: 'assistant', content: `[${event.role}] ${event.content}` })
    }
  }

  function submitHitlDecision(decision: 'approve' | 'refine' | 'reject', feedback?: string) {
    isHitlRequired.value = false
    hitlCheckpoint.value = null
    
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'hitl_response',
        decision,
        feedback: feedback || ''
      }))
    }
  }

  // Connect automatically on store initialization
  if (import.meta.env.MODE !== 'test') {
    connect()
  }

  let wakeWordWs: WebSocket | null = null
  let wwAudioContext: AudioContext | null = null
  let wwMicrophone: MediaStreamAudioSourceNode | null = null
  let wwProcessor: AudioWorkletNode | null = null
  let wwStream: MediaStream | null = null

  function startAutoListen() {
    if (isAutoListenEnabled.value) return
    isAutoListenEnabled.value = true
    isWakeWordTriggered.value = false

    // Create AudioContext immediately on user click to avoid browser suspension
    wwAudioContext = new AudioContext({ sampleRate: 16000 })
    
    // Convert ws://localhost:8000/ws/debate to /ws/audio/wake-word
    let wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/debate'
    wsUrl = wsUrl.replace('/ws/debate', '/ws/audio/wake-word')
    
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

        wwProcessor.port.onmessage = (e: MessageEvent<Float32Array>) => {
          if (wakeWordWs?.readyState !== WebSocket.OPEN) return
          
          // Do not listen for wake word if we are currently recording
          if (isRecording.value) return

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

    wakeWordWs.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'WAKE_WORD_DETECTED') {
          console.log('[WW] Wake word detected!')
          stopTts() // Interrupt any ongoing TTS
          isWakeWordTriggered.value = true // UI should watch this to start recording
          
          // Reset after a short delay so it can be triggered again later
          setTimeout(() => {
            isWakeWordTriggered.value = false
          }, 1000)
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

  return {
    isConnected,
    isDebating,
    isHitlRequired,
    hitlCheckpoint,
    messages,
    rawEvents,
    draftMessage,
    agents,
    isAgentsLoaded,
    isTtsPlaying,
    activeTtsRole,
    isVoiceOutputEnabled,
    isAutoListenEnabled,
    isRecording,
    isWakeWordTriggered,
    globalAudioPlayer,
    globalAnalyser,
    unlockAudioContext,
    playTtsAudioChunk,
    stopTts,
    loadAgents,
    loadDebate,
    connect,
    startDebate,
    uploadFile,
    handleSupervisorEvent,
    submitHitlDecision,
    startAutoListen,
    stopAutoListen,
    get ws() { return ws } // Getter for testing purposes
  }
})
