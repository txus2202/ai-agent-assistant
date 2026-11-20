import { watch } from 'vue'
import { audioService } from '../services/audioService'
import { cleanTextForTts, splitTextIntoTtsChunks } from '../utils/ttsFilter'

interface TtsTextItem {
  id: string
  text: string
  role: string
  sessionId: number
}

interface TtsAudioItem {
  id: string
  audio: ArrayBuffer
  role: string
  sessionId: number
}

export interface TtsPlaybackBridge {
  isVoiceOutputEnabled: boolean
  isTtsPlaying: boolean
  activeTtsRole: string | null
  addReadingAgentRole?: (role?: string | null) => void
  removeReadingAgentRole?: (role?: string | null) => void
  playTtsAudioChunk?: (audio: ArrayBuffer) => Promise<void>
  stopTts: () => void
}

export function useTtsPlaybackQueue(
  bridge: TtsPlaybackBridge,
  synthesizeSpeech: (
    text: string,
    addSilence: boolean,
    signal?: AbortSignal,
  ) => Promise<ArrayBuffer> = (text, addSilence, signal) =>
    audioService.synthesizeSpeech(text, addSilence, signal),
) {
  let ttsSessionId = 0
  let prefetchAbortController: AbortController | null = null
  let ttsTextQueue: TtsTextItem[] = []
  let ttsAudioQueue: TtsAudioItem[] = []
  let isPrefetching = false
  let isPlayingAudio = false

  const clearTtsQueues = () => {
    ttsSessionId++
    if (prefetchAbortController) {
      try {
        prefetchAbortController.abort()
      } catch {}
      prefetchAbortController = null
    }
    ttsTextQueue = []
    ttsAudioQueue = []
    isPrefetching = false
    isPlayingAudio = false
  }

  watch(
    () => bridge.isTtsPlaying,
    (isPlaying) => {
      if (!isPlaying) {
        clearTtsQueues()
      }
    },
    { flush: 'sync' },
  )

  const isTtsSessionActive = (session: number) => session === ttsSessionId && bridge.isTtsPlaying

  const finalizeAgentReadingIfDone = (role: string, currentSession: number) => {
    const stillHasAudio = ttsAudioQueue.some(
      (a) => a.role === role && a.sessionId === currentSession,
    )
    const stillHasText = ttsTextQueue.some(
      (t) => t.role === role && t.sessionId === currentSession,
    )
    if (!stillHasAudio && !stillHasText) {
      bridge.removeReadingAgentRole?.(role)
    }
  }

  const playNextAudio = async () => {
    if (isPlayingAudio) return

    if (ttsAudioQueue.length === 0) {
      if (ttsTextQueue.length === 0 && !isPrefetching) {
        bridge.stopTts()
      }
      return
    }

    if (!bridge.isTtsPlaying) return

    const currentSession = ttsSessionId
    isPlayingAudio = true
    const currentItem = ttsAudioQueue.shift()
    if (!currentItem) {
      isPlayingAudio = false
      return
    }

    if (currentItem.sessionId !== currentSession) {
      isPlayingAudio = false
      return
    }

    bridge.activeTtsRole = currentItem.role

    try {
      await bridge.playTtsAudioChunk?.(currentItem.audio)
    } catch (e) {
      console.error('Play error:', e)
    } finally {
      isPlayingAudio = false
    }

    if (currentSession !== ttsSessionId) return

    finalizeAgentReadingIfDone(currentItem.role, currentSession)

    if (isTtsSessionActive(currentSession)) {
      playNextAudio().catch((err) => {
        console.error('Error playing next audio chunk:', err)
      })
    }
  }

  const handlePrefetchAudioResult = (
    audioBuffer: ArrayBuffer,
    item: TtsTextItem,
    currentSession: number,
  ) => {
    if (!isTtsSessionActive(currentSession)) return
    ttsAudioQueue.push({
      id: item.id,
      audio: audioBuffer,
      role: item.role,
      sessionId: currentSession,
    })
    if (bridge.isTtsPlaying && !isPlayingAudio && currentSession === ttsSessionId) {
      playNextAudio().catch((err) => {
        console.error('Error starting audio playback:', err)
      })
    }
  }

  const prefetchTtsQueue = async () => {
    if (ttsTextQueue.length === 0) {
      isPrefetching = false
      return
    }

    const currentSession = ttsSessionId
    isPrefetching = true
    const item = ttsTextQueue.shift()
    if (!item) {
      isPrefetching = false
      return
    }

    try {
      prefetchAbortController = new AbortController()
      const audioBuffer = await synthesizeSpeech(
        item.text,
        false,
        prefetchAbortController.signal,
      )
      if (isTtsSessionActive(currentSession)) {
        handlePrefetchAudioResult(audioBuffer, item, currentSession)
      }
    } catch (e: unknown) {
      const isAbort = Boolean(e && typeof e === 'object' && 'name' in e && e.name === 'AbortError')
      if (!isAbort) {
        console.error('Error synthesizing speech:', e)
      }
    } finally {
      const hasMore = isTtsSessionActive(currentSession) && ttsTextQueue.length > 0
      if (hasMore) {
        prefetchTtsQueue().catch((err) => {
          console.error('Error prefetching next sentence:', err)
        })
      } else if (currentSession === ttsSessionId) {
        isPrefetching = false
      }
    }
  }

  const enqueueCleanTextForSpeech = (text: string, role?: string) => {
    if (!bridge.isVoiceOutputEnabled || !text) return
    const clean = cleanTextForTts(text)
    if (!clean) return

    const targetRole = role || bridge.activeTtsRole || 'supervisor'
    bridge.isTtsPlaying = true
    if (!bridge.activeTtsRole) {
      bridge.activeTtsRole = targetRole
    }
    bridge.addReadingAgentRole?.(targetRole)

    const chunks = splitTextIntoTtsChunks(clean)
    const currentSession = ttsSessionId
    chunks.forEach((chunk) => {
      ttsTextQueue.push({
        id: crypto.randomUUID(),
        text: chunk,
        role: targetRole,
        sessionId: currentSession,
      })
    })

    if (!isPrefetching) {
      prefetchTtsQueue().catch((err) => {
        console.error('Error prefetching TTS queue:', err)
      })
    }
  }

  const queueTtsSentence = (sentence: string, role?: string) => {
    enqueueCleanTextForSpeech(sentence, role)
  }

  const playVoiceResponse = (text: string, role?: string) => {
    enqueueCleanTextForSpeech(text, role)
  }

  return {
    clearTtsQueues,
    queueTtsSentence,
    playVoiceResponse,
  }
}

