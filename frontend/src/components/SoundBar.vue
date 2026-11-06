<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useDebateStore } from '../stores/debate'

const props = withDefaults(defineProps<{
  activeAgentColor?: string
  isDebating?: boolean
  showViewSwitch?: boolean
  listenWakeWord?: boolean
}>(), {
  activeAgentColor: '#f59e0b',
  isDebating: false,
  showViewSwitch: false,
  listenWakeWord: false
})

const emit = defineEmits<{
  (e: 'submit-draft'): void
  (e: 'open-voice'): void
}>()

const store = useDebateStore()

const isRecording = ref(false)
const audioChunks = ref<Blob[]>([])
const mediaRecorder = ref<MediaRecorder | null>(null)
const waveformCanvasRef = ref<HTMLCanvasElement | null>(null)

let waveAnimationFrameId = 0
let isComponentUnmounted = false
let waveOffset = 0

// Silence detection references
let silenceTimeout: ReturnType<typeof setTimeout> | null = null
let initialDelayTimeout: ReturnType<typeof setTimeout> | null = null
let audioContext: AudioContext | null = null
let analyser: AnalyserNode | null = null
let microphone: MediaStreamAudioSourceNode | null = null
let silenceCheckInterval: ReturnType<typeof setInterval> | null = null

const toggleRecording = async () => {
  if (isRecording.value) {
    if (mediaRecorder.value && mediaRecorder.value.state !== 'inactive') {
      mediaRecorder.value.stop()
    }
    isRecording.value = false
    store.isRecording = false
    stopSilenceDetection()
    return
  }

  try {
    store.stopTts()
    store.unlockAudioContext()

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const recorder = new MediaRecorder(stream)
    audioChunks.value = []

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) audioChunks.value.push(e.data)
    }

    recorder.onstop = async () => {
      isRecording.value = false
      store.isRecording = false
      stopSilenceDetection()
      const audioBlob = new Blob(audioChunks.value, { type: 'audio/webm' })
      stream.getTracks().forEach(t => t.stop())
      if (!isComponentUnmounted) {
        await uploadAudioForTranscription(audioBlob)
      }
    }

    recorder.start()
    mediaRecorder.value = recorder
    isRecording.value = true
    store.isRecording = true

    startSilenceDetection(stream)
  } catch (err) {
    console.error("Error accessing microphone:", err)
    alert("No se pudo acceder al micrófono para dictado de voz.")
  }
}

const uploadAudioForTranscription = async (blob: Blob) => {
  const formData = new FormData()
  formData.append('file', blob, 'recording.webm')

  try {
    const response = await fetch('/api/audio/transcribe', {
      method: 'POST',
      body: formData
    })

    if (response.ok) {
      const data = await response.json()
      if (data.text) {
        store.draftMessage += (store.draftMessage ? ' ' : '') + data.text
        emit('submit-draft')
      }
    } else {
      console.error("Transcription failed")
    }
  } catch (e) {
    console.error("Transcription error:", e)
  }
}

const startSilenceDetection = (stream: MediaStream) => {
  initialDelayTimeout = setTimeout(() => {
    if (!isRecording.value) return

    audioContext = new AudioContext()
    analyser = audioContext.createAnalyser()
    analyser.minDecibels = -70
    analyser.smoothingTimeConstant = 0.2
    analyser.fftSize = 256

    microphone = audioContext.createMediaStreamSource(stream)
    microphone.connect(analyser)

    const dataArray = new Uint8Array(analyser.frequencyBinCount)

    const checkSilence = () => {
      if (!isRecording.value || !analyser) return

      analyser.getByteFrequencyData(dataArray)
      let sum = 0
      for (const value of dataArray) {
        sum += value
      }
      const average = sum / dataArray.length

      if (average > 3) {
        if (silenceTimeout) {
          clearTimeout(silenceTimeout)
          silenceTimeout = null
        }
      } else if (!silenceTimeout) {
        silenceTimeout = setTimeout(() => {
          if (isRecording.value) {
            console.log("Silence detected, auto-submitting...")
            toggleRecording()
          }
        }, 2000)
      }
    }

    silenceCheckInterval = setInterval(checkSilence, 100)
  }, 1000)
}

const stopSilenceDetection = () => {
  if (initialDelayTimeout) {
    clearTimeout(initialDelayTimeout)
    initialDelayTimeout = null
  }
  if (silenceTimeout) {
    clearTimeout(silenceTimeout)
    silenceTimeout = null
  }
  if (silenceCheckInterval) {
    clearInterval(silenceCheckInterval)
    silenceCheckInterval = null
  }
  if (microphone) {
    microphone.disconnect()
    microphone = null
  }
  if (audioContext && audioContext.state !== 'closed') {
    audioContext.close().catch(() => {})
    audioContext = null
  }
  analyser = null
}

const getActiveAudioSource = (isLight: boolean): { activeAnalyser: AnalyserNode | null; waveColor: string } => {
  if (isRecording.value && analyser) {
    return {
      activeAnalyser: analyser,
      waveColor: isLight ? '#1e293b' : '#ffffff'
    }
  }
  if (store.isTtsPlaying && store.globalAnalyser) {
    return {
      activeAnalyser: store.globalAnalyser,
      waveColor: props.activeAgentColor
    }
  }
  return {
    activeAnalyser: null,
    waveColor: isLight ? '#334155' : '#ffffff'
  }
}

const drawActiveWaveform = (
  wCtx: CanvasRenderingContext2D,
  activeAnalyser: AnalyserNode,
  width: number,
  height: number,
  waveColor: string
) => {
  const dataArray = new Uint8Array(activeAnalyser.frequencyBinCount)
  activeAnalyser.getByteTimeDomainData(dataArray)

  wCtx.strokeStyle = waveColor
  wCtx.lineWidth = 2
  wCtx.beginPath()

  const sliceWidth = (width * 1.0) / activeAnalyser.frequencyBinCount
  let x = 0

  for (let i = 0; i < activeAnalyser.frequencyBinCount; i++) {
    const v = dataArray[i]! / 128.0
    const y = (v * height) / 2

    if (i === 0) {
      wCtx.moveTo(x, y)
    } else {
      wCtx.lineTo(x, y)
    }
    x += sliceWidth
  }
  wCtx.stroke()
}

const drawIdleWaveform = (
  wCtx: CanvasRenderingContext2D,
  width: number,
  centerY: number,
  isLight: boolean
) => {
  wCtx.strokeStyle = isLight ? 'rgba(100, 116, 139, 0.45)' : 'rgba(255, 255, 255, 0.25)'
  wCtx.lineWidth = 1.2
  wCtx.beginPath()
  wCtx.moveTo(0, centerY)
  wCtx.lineTo(width, centerY)
  wCtx.stroke()

  const pulseX = (waveOffset * 30) % width
  wCtx.beginPath()
  wCtx.arc(pulseX, centerY, 2.5, 0, Math.PI * 2)
  wCtx.fillStyle = isLight ? '#0f172a' : '#ffffff'
  wCtx.fill()

  waveOffset += 0.08
}

const animateWaveform = () => {
  if (!waveformCanvasRef.value) return
  const wCanvas = waveformCanvasRef.value
  const wCtx = wCanvas.getContext('2d')
  if (!wCtx) return

  wCtx.clearRect(0, 0, wCanvas.width, wCanvas.height)
  const isLight = typeof document !== 'undefined' && document.documentElement.classList.contains('light')
  const { activeAnalyser, waveColor } = getActiveAudioSource(isLight)

  if (activeAnalyser) {
    drawActiveWaveform(wCtx, activeAnalyser, wCanvas.width, wCanvas.height, waveColor)
  } else {
    drawIdleWaveform(wCtx, wCanvas.width, wCanvas.height / 2, isLight)
  }

  waveAnimationFrameId = requestAnimationFrame(animateWaveform)
}

watch(() => store.isWakeWordTriggered, (triggered) => {
  if (props.listenWakeWord && triggered && !isRecording.value) {
    toggleRecording()
  }
})

watch(() => store.isRecording, (recording) => {
  if (!recording && isRecording.value) {
    if (mediaRecorder.value && mediaRecorder.value.state !== 'inactive') {
      mediaRecorder.value.stop()
    }
    isRecording.value = false
    stopSilenceDetection()
  }
})

const voiceStateText = computed(() => {
  if (isRecording.value) {
    return 'ESTADO VOZ: ESCUCHANDO ORDEN'
  }
  if (store.isTtsPlaying) {
    return 'ESTADO VOZ: ACTIVO'
  }
  if (store.isAutoListenEnabled) {
    return 'ESTADO VOZ: ESPERANDO WAKE WORD'
  }
  return 'ESTADO VOZ: EN REPOSO'
})

const voiceDotStyle = computed(() => {
  if (isRecording.value) {
    return { backgroundColor: '#ffffff', boxShadow: '0 0 8px #ffffff' }
  } else if (store.isTtsPlaying) {
    return {
      backgroundColor: props.activeAgentColor,
      boxShadow: `0 0 8px ${props.activeAgentColor}`
    }
  }
  return { backgroundColor: '#475569' }
})

onMounted(() => {
  animateWaveform()
})

onUnmounted(() => {
  isComponentUnmounted = true
  cancelAnimationFrame(waveAnimationFrameId)
  stopSilenceDetection()
  if (mediaRecorder.value && isRecording.value) {
    mediaRecorder.value.stop()
  }
})

defineExpose({
  toggleRecording
})
</script>

<template>
  <div class="w-full flex flex-col items-center gap-1.5" data-test="sound-bar">
    <!-- Row 1: MIC VOZ button + Waveform Canvas (both h-[44px]) + optional View Switch -->
    <div class="flex items-center gap-2.5 w-full">
      <!-- Microphone Button -->
      <button
        id="micButton"
        type="button"
        @click="toggleRecording"
        :class="isRecording ? 'border-red-500 bg-red-900/30' : 'border-slate-700 hover:border-cyan-400 bg-space-850 hover:bg-space-800'"
        class="relative group px-3 h-[44px] min-h-[44px] rounded-lg text-slate-300 hover:text-cyan-200 transition-all flex items-center space-x-2 shadow-md shrink-0 active:scale-95 border"
        title="Activar micrófono para hablar (Pulsa para hablar)"
      >
        <div v-if="isRecording" class="absolute w-2 h-2 rounded-full bg-red-500 -top-1 -right-1 animate-pulse"></div>
        <div class="w-7 h-7 rounded-full bg-space-900 flex items-center justify-center border border-slate-700 group-hover:border-cyan-400 shrink-0" id="micIconRing">
          <svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-mic w-3.5 h-3.5 text-cyan-400 group-hover:scale-110 transition"><path d="M12 19v3"></path><path d="M19 10v2a7 7 0 0 1-14 0v-2"></path><rect x="9" y="2" width="6" height="13" rx="3"></rect></svg>
        </div>
        <div class="text-left font-mono">
          <div class="text-[10px] font-bold text-cyan-300 uppercase tracking-wider flex items-center gap-1">
            <span>MIC VOZ</span>
          </div>
          <div class="text-[8px] text-slate-400" id="micStatusSub">{{ isRecording ? 'ESCUCHANDO...' : 'LISTO PARA ESCUCHAR' }}</div>
        </div>
      </button>

      <!-- Audio Spectrum Canvas (same height h-[44px] matching MIC button) -->
      <div class="flex-1 h-[44px] min-w-0 flex items-center">
        <canvas
          ref="waveformCanvasRef"
          id="waveformCanvas"
          class="w-full h-[44px] rounded-lg bg-space-950/70 border border-slate-800/80 block"
          width="400"
          height="44"
        ></canvas>
      </div>

      <!-- Optional 3D View Switch Button (for mobile chat header) -->
      <button
        v-if="showViewSwitch"
        type="button"
        data-test="soundbar-view-switch"
        @click="emit('open-voice')"
        class="h-[44px] px-2.5 rounded-lg bg-cyan-950/50 hover:bg-cyan-900/60 border border-cyan-500/30 text-cyan-400 font-mono text-xs flex items-center gap-1 shrink-0 transition-colors"
        title="Abrir Orbe de Voz 3D"
      >
        <span class="font-bold">3D</span>
        <span class="text-[10px]">&gt;</span>
      </button>
    </div>

    <!-- Row 2: Voice status caption, centered directly below button and waveform -->
    <div class="w-full flex items-center justify-center space-x-2 text-[10px] font-mono text-slate-400 pt-0.5">
      <span
        class="w-2 h-2 rounded-full transition-colors duration-300 shrink-0"
        id="voiceIndicatorDot"
        :style="voiceDotStyle"
      ></span>
      <span class="text-slate-400 font-mono tracking-tight" id="voiceStateCaption">{{ voiceStateText }}</span>
    </div>
  </div>
</template>

