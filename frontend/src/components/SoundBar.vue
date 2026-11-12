<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { ChevronDown } from '@lucide/vue'
import { useDebateStore } from '../stores/debate'
import { useTouchSwipe } from '../utils/touchSwipe'

const props = withDefaults(defineProps<{
  activeAgentColor?: string
  isDebating?: boolean
  showViewSwitch?: boolean
  listenWakeWord?: boolean
  collapsible?: boolean
  initialCollapsed?: boolean
}>(), {
  activeAgentColor: '#f59e0b',
  isDebating: false,
  showViewSwitch: false,
  listenWakeWord: false,
  collapsible: false,
  initialCollapsed: true
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

const isCollapsed = ref(props.initialCollapsed)
const soundBarContainerRef = ref<HTMLElement | null>(null)
const dockPanelRef = ref<HTMLElement | null>(null)

watch(() => props.initialCollapsed, (val) => {
  isCollapsed.value = val
})

watch(() => props.collapsible, (isCol) => {
  if (isCol && props.initialCollapsed) {
    isCollapsed.value = true
  }
})

const toggleCollapse = () => {
  if (!props.collapsible) return
  isCollapsed.value = !isCollapsed.value
}

const expand = () => {
  if (!props.collapsible) return
  isCollapsed.value = false
}

const collapse = () => {
  if (!props.collapsible) return
  isCollapsed.value = true
}

useTouchSwipe(soundBarContainerRef, {
  onSwipeUp: () => {
    if (props.collapsible && isCollapsed.value) {
      expand()
    }
  },
  onSwipeDown: () => {
    if (props.collapsible && !isCollapsed.value) {
      collapse()
    }
  }
})

const initMicrophoneAudio = async (stream: MediaStream) => {
  try {
    const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
    if (!AudioCtx) return
    if (!audioContext || audioContext.state === 'closed') {
      audioContext = new AudioCtx()
    }
    if (audioContext.state === 'suspended') {
      await audioContext.resume().catch(() => {})
    }

    analyser = audioContext.createAnalyser()
    analyser.minDecibels = -70
    analyser.smoothingTimeConstant = 0.2
    analyser.fftSize = 256

    microphone = audioContext.createMediaStreamSource(stream)
    microphone.connect(analyser)
  } catch (err) {
    console.warn("Could not setup mic analyser", err)
  }
}

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

  if (props.collapsible && isCollapsed.value) {
    expand()
  }

  try {
    store.stopTts()
    store.unlockAudioContext()

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    await initMicrophoneAudio(stream)

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

    startSilenceDetection()
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

const startSilenceDetection = () => {
  initialDelayTimeout = setTimeout(() => {
    if (!isRecording.value || !analyser) return

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
            toggleRecording().catch(err => {
              console.error("Error toggling recording on silence:", err)
            })
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
  wCtx.strokeStyle = isLight ? 'rgba(100, 116, 139, 0.45)' : 'rgba(6, 182, 212, 0.35)'
  wCtx.lineWidth = 1.2
  wCtx.beginPath()
  wCtx.moveTo(0, centerY)
  wCtx.lineTo(width, centerY)
  wCtx.stroke()

  const pulseX = (waveOffset * 30) % width
  wCtx.beginPath()
  wCtx.arc(pulseX, centerY, 2.5, 0, Math.PI * 2)
  wCtx.fillStyle = isLight ? '#0f172a' : '#00e5ff'
  wCtx.fill()

  waveOffset += 0.08
}

const animateWaveform = () => {
  if (!waveformCanvasRef.value) return
  const wCanvas = waveformCanvasRef.value
  if (wCanvas.clientWidth > 0 && wCanvas.width !== wCanvas.clientWidth) {
    wCanvas.width = wCanvas.clientWidth
  }
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
    if (props.collapsible && isCollapsed.value) {
      expand()
    }
    toggleRecording().catch(err => {
      console.error("Error toggling recording on wake word:", err)
    })
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
  toggleRecording,
  isRecording,
  isCollapsed,
  toggleCollapse,
  expand,
  collapse
})
</script>

<template>
  <div
    ref="soundBarContainerRef"
    class="w-full select-none"
    :class="collapsible ? 'relative h-[34px] z-30 pointer-events-auto' : 'flex flex-col items-center'"
    data-test="sound-bar"
  >
    <!-- Overlay Dock Panel: Anchored to bottom-0, expands upwards on top of screen content without displacing elements -->
    <div
      ref="dockPanelRef"
      :class="collapsible ? 'absolute bottom-0 left-0 w-full flex flex-col items-center bg-[#080e1a]/95 backdrop-blur-md shadow-[0_-8px_24px_rgba(0,0,0,0.6)] border-t border-cyan-900/50 pointer-events-auto touch-none' : 'w-full flex flex-col items-center gap-1.5'"
    >
      <!-- Collapsible Handle Bar (Visible when props.collapsible is true) -->
      <div
        v-if="collapsible"
        data-test="soundbar-collapse-handle"
        role="button"
        tabindex="0"
        @click="toggleCollapse"
        @keydown.enter.space.prevent="toggleCollapse"
        class="w-full relative flex items-center justify-between px-3 py-1 cursor-pointer select-none min-h-[34px] touch-none border-b transition-colors duration-200"
        :class="isCollapsed ? 'border-transparent hover:bg-space-850/60' : 'border-slate-800/40'"
        title="Pulsa o desliza para alternar"
      >
        <!-- Left: Mini status ONLY when collapsed (never rendered when deployed to avoid stray dot over mic) -->
        <div
          v-if="isCollapsed"
          class="flex items-center gap-2 min-w-0 max-w-[38%] sm:max-w-[42%] z-0 transition-opacity duration-200"
        >
          <span
            class="w-2 h-2 rounded-full transition-colors duration-300 shrink-0"
            :style="voiceDotStyle"
          ></span>
          <span class="text-[10px] font-mono text-slate-300 truncate">
            {{ isRecording ? 'GRABANDO...' : voiceStateText }}
          </span>
        </div>
        <div v-else class="w-6"></div>

        <!-- Center: Toggle arrow button - STRICTLY CENTERED AT 50% -->
        <div class="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-10 flex items-center justify-center">
          <button
            type="button"
            data-test="soundbar-collapse-toggle"
            @click.stop="toggleCollapse"
            class="min-w-[48px] min-h-[34px] px-4 py-1 rounded hover:bg-space-800 text-slate-400 hover:text-cyan-300 transition-colors flex items-center justify-center group"
            :title="isCollapsed ? 'Desplegar barra de sonido (o desliza hacia arriba)' : 'Colapsar barra de sonido (o desliza hacia abajo)'"
            :aria-expanded="!isCollapsed"
            aria-label="Alternar colapso de la barra de sonido"
          >
            <ChevronDown
              class="w-4 h-4 transition-transform duration-300 ease-out"
              :class="[
                isCollapsed ? 'rotate-180 text-cyan-400 group-hover:text-cyan-300' : 'rotate-0 text-slate-400 group-hover:text-cyan-300',
                { 'text-red-400 animate-pulse': isRecording && isCollapsed }
              ]"
            />
          </button>
        </div>

        <!-- Right: Minimal indicator ONLY when collapsed -->
        <div
          v-if="isCollapsed"
          class="text-[10px] font-mono uppercase tracking-wider shrink-0 z-0 transition-opacity duration-200"
        >
          <span class="text-slate-300 font-bold">MIC</span>
        </div>
        <div v-else class="w-6"></div>
      </div>

      <!-- Main SoundBar Content: Collapsible Body with Smooth Expand/Collapse Animation -->
      <Transition
        enter-active-class="transition-all duration-300 ease-out overflow-hidden"
        enter-from-class="opacity-0 max-h-0 !py-0"
        enter-to-class="opacity-100 max-h-[140px] py-1"
        leave-active-class="transition-all duration-300 ease-in-out overflow-hidden"
        leave-from-class="opacity-100 max-h-[140px] py-1"
        leave-to-class="opacity-0 max-h-0 !py-0"
      >
        <div
          v-show="!collapsible || !isCollapsed"
          data-test="soundbar-body"
          class="w-full flex flex-col items-center gap-1.5"
          :class="collapsible ? 'px-3 pb-2 pt-1' : ''"
        >
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
      </Transition>
    </div>
  </div>
</template>

