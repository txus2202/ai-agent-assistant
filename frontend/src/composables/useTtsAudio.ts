import { ref } from 'vue'
import { normalizeAgentRole } from '../utils/debateHelpers'
import { findSentenceSplitIndex, getToolSpokenFallback } from '../utils/ttsFilter'

// Builds a valid 0.1s silent 8-bit mono WAV (Safari rejects malformed/tiny headers)
function buildSilentWavUrl(): string {
  const samples = 800
  const buf = new ArrayBuffer(44 + samples)
  const v = new DataView(buf)
  const str = (o: number, s: string) => {
    for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.codePointAt(i) ?? 0)
  }
  str(0, 'RIFF')
  v.setUint32(4, 36 + samples, true)
  str(8, 'WAVE')
  str(12, 'fmt ')
  v.setUint32(16, 16, true)
  v.setUint16(20, 1, true)
  v.setUint16(22, 1, true)
  v.setUint32(24, 8000, true)
  v.setUint32(28, 8000, true)
  v.setUint16(32, 1, true)
  v.setUint16(34, 8, true)
  str(36, 'data')
  v.setUint32(40, samples, true)
  new Uint8Array(buf, 44).fill(128)
  return URL.createObjectURL(new Blob([buf], { type: 'audio/wav' }))
}

function isSupervisorIdentifier(normalizedRole: string): boolean {
  return normalizedRole === 'supervisor' || normalizedRole === 'atenea'
}

export function rolesMatchForTts(roleA: string, roleB: string): boolean {
  if (roleA === roleB) return true
  return isSupervisorIdentifier(roleA) && isSupervisorIdentifier(roleB)
}

export interface TtsEngineHooks {
  onRoleReadingStart?: (normRole: string) => void
  onRoleReadingEnd?: (role: string, normRole: string) => void
  onAfterStop?: () => void
  onGestureUnlock?: () => void
}

export function createTtsAudioEngine(hooks: TtsEngineHooks = {}) {
  const isTtsPlaying = ref(false)
  const activeTtsRole = ref<string | null>(null)
  const readingAgentRoles = ref<string[]>([])
  const isVoiceOutputEnabled = ref(true)
  const globalAudioPlayer = new Audio()
  globalAudioPlayer.crossOrigin = 'anonymous'

  let globalAudioContext: AudioContext | null = null
  const globalAnalyser = ref<AnalyserNode | null>(null)
  let currentTtsSource: AudioBufferSourceNode | null = null
  let audioPlaySessionId = 0
  let silentWavUrl: string | null = null
  const ttsStopCallbacks: Array<() => void> = []

  // Streaming chunk splitting state
  let ttsStreamBuffer = ''
  let isInsideCodeFence = false
  let codeFenceType = ''
  let hasSpokenInCurrentMessage = false
  const ttsChunkCallbacks: Array<(chunk: string, role?: string) => void> = []

  function isAgentReading(role?: string | null): boolean {
    if (!role || !isVoiceOutputEnabled.value) return false
    const norm = (normalizeAgentRole(role) || role).toLowerCase()
    return readingAgentRoles.value.some((r) => {
      const normR = (normalizeAgentRole(r) || r).toLowerCase()
      return rolesMatchForTts(norm, normR)
    })
  }

  function addReadingAgentRole(role?: string | null) {
    if (!role || !isVoiceOutputEnabled.value) return
    const norm = normalizeAgentRole(role) || role
    if (!isAgentReading(norm)) {
      readingAgentRoles.value.push(norm)
    }
    hooks.onRoleReadingStart?.(norm)
  }

  function removeReadingAgentRole(role?: string | null) {
    if (!role) return
    const norm = (normalizeAgentRole(role) || role).toLowerCase()
    readingAgentRoles.value = readingAgentRoles.value.filter((r) => {
      const normR = (normalizeAgentRole(r) || r).toLowerCase()
      return !rolesMatchForTts(norm, normR)
    })
    hooks.onRoleReadingEnd?.(role, norm)
    if (activeTtsRole.value) {
      const currentNorm = (normalizeAgentRole(activeTtsRole.value) || activeTtsRole.value).toLowerCase()
      if (rolesMatchForTts(norm, currentNorm)) {
        activeTtsRole.value = readingAgentRoles.value[0] || null
      }
    }
  }

  function clearReadingAgentRoles() {
    const wasReading = [...readingAgentRoles.value]
    readingAgentRoles.value = []
    wasReading.forEach((role) => {
      const norm = (normalizeAgentRole(role) || role).toLowerCase()
      hooks.onRoleReadingEnd?.(role, norm)
    })
  }

  function onTtsStop(callback: () => void): () => void {
    ttsStopCallbacks.push(callback)
    return () => {
      const idx = ttsStopCallbacks.indexOf(callback)
      if (idx !== -1) {
        ttsStopCallbacks.splice(idx, 1)
      }
    }
  }

  function onTtsChunkReady(callback: (chunk: string, role?: string) => void): () => void {
    ttsChunkCallbacks.push(callback)
    return () => {
      const idx = ttsChunkCallbacks.indexOf(callback)
      if (idx !== -1) {
        ttsChunkCallbacks.splice(idx, 1)
      }
    }
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

  function resetTtsStreamState() {
    ttsStreamBuffer = ''
    isInsideCodeFence = false
    codeFenceType = ''
    hasSpokenInCurrentMessage = false
  }

  function clearTtsStreamBuffer() {
    ttsStreamBuffer = ''
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

  function getOrCreateAudioContext(): AudioContext | null {
    if (typeof window === 'undefined') return null
    try {
      if (!globalAudioContext) {
        const AudioCtx =
          window.AudioContext ||
          (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
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
      console.warn('Could not initialize AudioContext', e)
      return null
    }
  }

  function unlockAudioContext() {
    try {
      if (!silentWavUrl && typeof window !== 'undefined') silentWavUrl = buildSilentWavUrl()
      if (silentWavUrl && globalAudioPlayer) {
        const unlockUrl = silentWavUrl
        globalAudioPlayer.src = unlockUrl
        globalAudioPlayer
          .play()
          .then(() => {
            if (globalAudioPlayer.src === unlockUrl) globalAudioPlayer.pause()
          })
          .catch(() => {})
      }
    } catch {}

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
      console.warn('Could not unlock Web Audio Context', e)
    }
  }

  async function playTtsAudioChunk(audioData: ArrayBuffer): Promise<void> {
    const session = audioPlaySessionId
    if (!isTtsPlaying.value) return
    const ctx = getOrCreateAudioContext()
    if (!ctx?.decodeAudioData) return

    if (ctx.state === 'suspended') {
      await ctx.resume().catch(() => {})
    }

    const copy = audioData.slice(0)
    const audioBuffer = await ctx.decodeAudioData(copy)

    if (session !== audioPlaySessionId || !isTtsPlaying.value) {
      return
    }

    return new Promise((resolve) => {
      if (session !== audioPlaySessionId || !isTtsPlaying.value) {
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
    audioPlaySessionId++
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

    for (const cb of ttsStopCallbacks) {
      try {
        cb()
      } catch (err) {
        console.error('Error in ttsStopCallback:', err)
      }
    }

    hooks.onAfterStop?.()
  }

  if (typeof window !== 'undefined') {
    const unlockOnGesture = () => {
      unlockAudioContext()
      hooks.onGestureUnlock?.()
      window.removeEventListener('pointerdown', unlockOnGesture)
      window.removeEventListener('keydown', unlockOnGesture)
      window.removeEventListener('touchstart', unlockOnGesture)
    }
    window.addEventListener('pointerdown', unlockOnGesture, { passive: true, once: true })
    window.addEventListener('keydown', unlockOnGesture, { passive: true, once: true })
    window.addEventListener('touchstart', unlockOnGesture, { passive: true, once: true })
  }

  return {
    isTtsPlaying,
    activeTtsRole,
    readingAgentRoles,
    isVoiceOutputEnabled,
    globalAudioPlayer,
    globalAnalyser,
    isAgentReading,
    addReadingAgentRole,
    removeReadingAgentRole,
    clearReadingAgentRoles,
    onTtsStop,
    onTtsChunkReady,
    feedTtsStreamingChunk,
    flushTtsStreamingBuffer,
    resetTtsStreamState,
    clearTtsStreamBuffer,
    unlockAudioContext,
    playTtsAudioChunk,
    stopTts,
  }
}
