import { ref } from 'vue'
import { createWakeWordWsClient } from '../services/wakeWordWsClient'
import type { HitlDecisionType } from '../utils/debateHelpers'

export interface WakeWordDetectionPayload {
  agent_role?: string
  display_name?: string
}

export interface UseWakeWordOptions {
  isHitlRequired: () => boolean
  onSilenceCommand: () => void
  onHitlDecisionCommand: (decision: HitlDecisionType) => void
  onHitlRefineCommand: () => void
  onToggleHitlTargetAgent: (identifier: string) => void
  onWakeWordInterrupt: () => void
  onAgentWakeWordSelected: (role: string) => void
}

const PCM_WORKLET_CODE = `
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

const HITL_VOICE_DECISION_MAP: Record<string, HitlDecisionType> = {
  approve: 'approve',
  reject: 'reject',
  finish: 'finish',
  consolidate: 'consolidate',
  retry: 'retry',
  divert: 'divert',
}

export function useWakeWord(options: UseWakeWordOptions) {
  const isRecording = ref(false)
  const isAutoListenEnabled = ref(false)
  const isWakeWordTriggered = ref(false)

  const wakeWordWsClient = createWakeWordWsClient()
  let wwAudioContext: AudioContext | null = null
  let wwMicrophone: MediaStreamAudioSourceNode | null = null
  let wwProcessor: AudioWorkletNode | null = null
  let wwStream: MediaStream | null = null

  function resumeSuspendedContext() {
    if (wwAudioContext?.state === 'suspended') {
      wwAudioContext.resume().catch(() => {})
    }
  }

  function resetWakeWordSession() {
    isWakeWordTriggered.value = false
    isRecording.value = false
    try {
      wakeWordWsClient.sendReset()
    } catch {}
    resumeSuspendedContext()
  }

  function handleHitlVoiceCommand(command: string) {
    if (!options.isHitlRequired()) return

    if (command === 'refine') {
      options.onHitlRefineCommand()
      isWakeWordTriggered.value = true
      setTimeout(() => {
        isWakeWordTriggered.value = false
      }, 1000)
      return
    }

    const decision = HITL_VOICE_DECISION_MAP[command]
    if (decision) {
      options.onHitlDecisionCommand(decision)
    }
  }

  function handleWakeWordDetected(data: WakeWordDetectionPayload) {
    console.log('[WW] Wake word detected for agent:', data.agent_role || 'supervisor')
    if (options.isHitlRequired()) {
      const targetIdentifier = data.agent_role || data.display_name
      if (targetIdentifier) {
        options.onToggleHitlTargetAgent(targetIdentifier)
      }
      return
    }

    options.onWakeWordInterrupt()
    if (data.agent_role) {
      options.onAgentWakeWordSelected(data.agent_role)
    }
    isWakeWordTriggered.value = true

    setTimeout(() => {
      isWakeWordTriggered.value = false
    }, 1000)
  }

  function stopAutoListen() {
    isAutoListenEnabled.value = false
    isWakeWordTriggered.value = false

    wakeWordWsClient.close()
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
      wwStream.getTracks().forEach((t) => t.stop())
      wwStream = null
    }
  }

  function startAutoListen() {
    if (isAutoListenEnabled.value) return
    isAutoListenEnabled.value = true
    isWakeWordTriggered.value = false

    // Create AudioContext immediately on user click to avoid browser suspension
    wwAudioContext = new AudioContext({ sampleRate: 16000 })

    wakeWordWsClient.connect({
      onOpen: async () => {
        console.log('[WW] Connected to wake-word stream')
        try {
          wwStream = await navigator.mediaDevices.getUserMedia({ audio: true })

          resumeSuspendedContext()
          if (!wwAudioContext) return

          wwMicrophone = wwAudioContext.createMediaStreamSource(wwStream)

          const workletUrl = URL.createObjectURL(
            new Blob([PCM_WORKLET_CODE], { type: 'application/javascript' }),
          )
          try {
            await wwAudioContext.audioWorklet.addModule(workletUrl)
          } finally {
            URL.revokeObjectURL(workletUrl)
          }

          wwProcessor = new AudioWorkletNode(wwAudioContext, 'pcm-capture-processor')
          wwMicrophone.connect(wwProcessor)

          // Connect through a zero-gain node to destination to keep the AudioWorklet clock running continuously
          try {
            const silentGain = wwAudioContext.createGain()
            silentGain.gain.value = 0
            wwProcessor.connect(silentGain)
            silentGain.connect(wwAudioContext.destination)
          } catch {}

          wwProcessor.port.onmessage = (e: MessageEvent<Float32Array>) => {
            if (!wakeWordWsClient.isOpen()) return
            if (isRecording.value) return

            resumeSuspendedContext()

            const inputData = e.data
            const pcm16 = new Int16Array(inputData.length)
            for (let i = 0; i < inputData.length; i++) {
              const s = Math.max(-1, Math.min(1, inputData[i] ?? 0))
              pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff
            }
            wakeWordWsClient.sendAudio(pcm16.buffer)
          }
        } catch (e) {
          console.error('[WW] Error accessing microphone for auto-listen', e)
          stopAutoListen()
        }
      },
      onMessage: (rawData) => {
        try {
          const data = JSON.parse(rawData) as {
            type?: string
            command?: string
            agent_role?: string
            display_name?: string
          }
          if (data.type === 'SILENCE_VOICE_COMMAND') {
            console.log('[WW] Silence voice command received')
            options.onSilenceCommand()
            return
          }
          if (data.type === 'HITL_VOICE_COMMAND' && data.command) {
            console.log('[WW] HITL Voice command received:', data.command)
            handleHitlVoiceCommand(data.command)
            return
          }
          if (data.type === 'WAKE_WORD_DETECTED') {
            handleWakeWordDetected(data)
          }
        } catch {}
      },
      onClose: () => {
        console.log('[WW] Disconnected from wake-word stream')
        stopAutoListen()
      },
    })
  }

  return {
    isRecording,
    isAutoListenEnabled,
    isWakeWordTriggered,
    startAutoListen,
    stopAutoListen,
    resetWakeWordSession,
    resumeSuspendedContext,
  }
}

