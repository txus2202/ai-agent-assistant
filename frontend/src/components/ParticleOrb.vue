<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'
import { useDebateStore } from '../stores/debate'

const store = useDebateStore()

const props = defineProps<{
  activeAgentColor: string // e.g. '#00e5ff'
  isDebating: boolean
  activeAgentIndex?: number // Optional index (0 to 5) to identify the agent
}>()

const emit = defineEmits<{
  (e: 'submit-draft'): void
}>()

const orbCanvasRef = ref<HTMLCanvasElement | null>(null)
const waveformCanvasRef = ref<HTMLCanvasElement | null>(null)
let ctx: CanvasRenderingContext2D | null = null
let animationFrameId: number
let waveAnimationFrameId: number
let isComponentUnmounted = false

// Cosmic Neural Orb Web Particle logic
const SPHERE_PARTICLE_COUNT = 800 // Reduced for Plexus performance
const AMBIENT_DUST_COUNT = 80
const TOTAL_AGENTS = 6
let BASE_RADIUS = 220
let orbWidth = 800
let orbHeight = 560

interface Particle3D {
  x: number; y: number; z: number; ox: number; oy: number; oz: number;
  size: number; alpha: number; linkDistance: number; phase: number;
  groupId: number; // To which agent this particle belongs
}

const particles: Particle3D[] = []
interface DustParticle {
  x: number; y: number; z: number; size: number;
  vx: number; vy: number; vz: number;
}

const ambientDust: DustParticle[] = []
let globalRotationY = 0
let globalRotationX = 0

const initParticles = () => {
  particles.length = 0
  ambientDust.length = 0

  for (let i = 0; i < SPHERE_PARTICLE_COUNT; i++) {
    const phi = Math.acos(1 - 2 * (i + 0.5) / SPHERE_PARTICLE_COUNT)
    const theta = Math.PI * (1 + Math.sqrt(5)) * i

    const xNorm = Math.sin(phi) * Math.cos(theta)
    const yNorm = Math.sin(phi) * Math.sin(theta)
    const zNorm = Math.cos(phi)
    // Safe: Math.random() is used only for cosmetic visual jitter, not for anything security-sensitive.
    const radOffset = (Math.random() - 0.45) * 36 // NOSONAR

    particles.push({
      ox: xNorm, oy: yNorm, oz: zNorm,
      x: 0, y: 0, z: 0,
      size: Math.random() * 1.5 + 0.8, // NOSONAR - cosmetic only // Slightly larger particles
      alpha: Math.random() * 0.5 + 0.3, // NOSONAR - cosmetic only
      linkDistance: 1 + radOffset / BASE_RADIUS,
      phase: Math.random() * Math.PI * 2, // NOSONAR - cosmetic only
      groupId: i % TOTAL_AGENTS // Divide particles equally among agents
    })
  }

  for (let i = 0; i < AMBIENT_DUST_COUNT; i++) {
    ambientDust.push({
      // NOSONAR below: Math.random() is used only for cosmetic particle placement/motion.
      x: (Math.random() - 0.5) * orbWidth * 1.5, // NOSONAR
      y: (Math.random() - 0.5) * orbHeight * 1.5, // NOSONAR
      z: (Math.random() - 0.5) * 800, // NOSONAR
      size: Math.random() * 2, // NOSONAR
      vx: (Math.random() - 0.5) * 0.4, // NOSONAR
      vy: (Math.random() - 0.5) * 0.4, // NOSONAR
      vz: (Math.random() - 0.5) * 0.4 // NOSONAR
    })
  }
}

const resizeCanvas = () => {
  if (!orbCanvasRef.value) return
  const canvas = orbCanvasRef.value
  const parent = canvas.parentElement
  if (!parent) return
  const rect = parent.getBoundingClientRect()
  orbWidth = canvas.width = (rect && rect.width > 200) ? Math.floor(rect.width) : 800
  orbHeight = canvas.height = (rect && rect.height > 200) ? Math.floor(rect.height) : 560
  BASE_RADIUS = Math.max(180, Math.min(235, Math.min(orbWidth, orbHeight) * 0.38))
  ctx = canvas.getContext('2d')
}

// Helper to convert hex color to RGB string
const getRgbFromHex = (hex: string): string => {
  let c = hex.replace('#', '')
  if (c.length === 3) c = c.split('').map(char => char + char).join('')
  const r = Number.parseInt(c.substring(0, 2), 16)
  const g = Number.parseInt(c.substring(2, 4), 16)
  const b = Number.parseInt(c.substring(4, 6), 16)
  return `${Number.isNaN(r) ? 255 : r}, ${Number.isNaN(g) ? 255 : g}, ${Number.isNaN(b) ? 255 : b}`
}

let currentExpansion = 1.0

const FAR_Z = -700
const WHITE_RGB = '255, 255, 255'

interface FrameState {
  cx: number
  cy: number
  speedMultiplier: number
  activeColorRGB: string
  currentAgentIndex: number
}

const project = (z: number) => 800 / (800 + z)

const isActiveGroup = (p: Particle3D, frame: FrameState) =>
  props.isDebating && p.groupId === frame.currentAgentIndex

const updateParticlePositions = (speedMultiplier: number) => {
  const cosY = Math.cos(globalRotationY)
  const sinY = Math.sin(globalRotationY)
  const cosX = Math.cos(globalRotationX)
  const sinX = Math.sin(globalRotationX)

  for (const p of particles) {
    const rx1 = p.ox * cosY - p.oz * sinY
    const rz1 = p.oz * cosY + p.ox * sinY
    const ry1 = p.oy * cosX - rz1 * sinX
    const rz2 = rz1 * cosX + p.oy * sinX

    p.phase += 0.02 * speedMultiplier
    const currentRadius = (BASE_RADIUS * p.linkDistance + Math.sin(p.phase) * 5) * currentExpansion

    p.x = rx1 * currentRadius
    p.y = ry1 * currentRadius
    p.z = rz2 * currentRadius
  }
}

const drawLink = (
  c: CanvasRenderingContext2D, p1: Particle3D, p2: Particle3D,
  distSq: number, color: string, isActive: boolean, frame: FrameState
) => {
  const persp1 = project(p1.z)
  const persp2 = project(p2.z)
  const alpha = (1 - Math.sqrt(distSq) / 50) * 0.3 * (isActive ? 0.8 : 0.3)
  c.beginPath()
  c.moveTo(frame.cx + p1.x * persp1, frame.cy + p1.y * persp1)
  c.lineTo(frame.cx + p2.x * persp2, frame.cy + p2.y * persp2)
  c.strokeStyle = `rgba(${color}, ${alpha})`
  c.stroke()
}

const drawConnectionsFor = (
  c: CanvasRenderingContext2D, i: number, frame: FrameState
) => {
  const p1 = particles[i]!
  const isActive = isActiveGroup(p1, frame)
  const color = isActive ? frame.activeColorRGB : WHITE_RGB

  // Only check connections for a subset to save performance
  for (let j = i + 1; j < particles.length; j += 2) {
    const p2 = particles[j]!
    if (p2.z < FAR_Z) continue
    const dx = p1.x - p2.x
    const dy = p1.y - p2.y
    const dz = p1.z - p2.z
    const distSq = dx * dx + dy * dy + dz * dz
    if (distSq < 2500) drawLink(c, p1, p2, distSq, color, isActive, frame)
  }
}

const drawConnections = (c: CanvasRenderingContext2D, frame: FrameState) => {
  c.lineWidth = 0.5
  for (let i = 0; i < particles.length; i++) {
    if (particles[i]!.z < FAR_Z) continue // Skip far particles for performance
    drawConnectionsFor(c, i, frame)
  }
}

const drawParticle = (c: CanvasRenderingContext2D, p: Particle3D, frame: FrameState) => {
  const perspective = project(p.z)
  const px = frame.cx + p.x * perspective
  const py = frame.cy + p.y * perspective
  const isActive = isActiveGroup(p, frame)
  const baseColor = isActive ? frame.activeColorRGB : WHITE_RGB

  const projSize = (isActive ? p.size * 1.5 : p.size) * perspective
  const depthAlpha = Math.max(0.05, Math.min(1, (p.z + BASE_RADIUS) / (BASE_RADIUS * 2.5)))
  const finalAlpha = isActive ? Math.min(1, p.alpha * depthAlpha * 2) : p.alpha * depthAlpha

  c.beginPath()
  c.arc(px, py, projSize, 0, Math.PI * 2)
  c.fillStyle = `rgba(${baseColor}, ${finalAlpha})`
  c.fill()

  if (!isActive) return
  // Subtle glow for active particles
  c.beginPath()
  c.arc(px, py, projSize * 3, 0, Math.PI * 2)
  c.fillStyle = `rgba(${baseColor}, ${finalAlpha * 0.2})`
  c.fill()
}

const drawParticles = (c: CanvasRenderingContext2D, frame: FrameState) => {
  for (const p of particles) {
    if (p.z > FAR_Z) drawParticle(c, p, frame)
  }
}

const wrap = (value: number, limit: number) => {
  if (value > limit) return -limit
  if (value < -limit) return limit
  return value
}

const drawAmbientDust = (c: CanvasRenderingContext2D, frame: FrameState) => {
  const color = props.isDebating ? frame.activeColorRGB : WHITE_RGB
  for (const d of ambientDust) {
    d.x = wrap(d.x + d.vx * frame.speedMultiplier, orbWidth)
    d.y = wrap(d.y + d.vy * frame.speedMultiplier, orbHeight)
    d.z += d.vz * frame.speedMultiplier

    if (d.z <= FAR_Z) continue
    const perspective = project(d.z)
    c.beginPath()
    c.arc(frame.cx + d.x * perspective, frame.cy + d.y * perspective, d.size * perspective, 0, Math.PI * 2)
    c.fillStyle = `rgba(${color}, ${0.1 * perspective})`
    c.fill()
  }
}

const animateOrb = () => {
  if (!ctx || !orbCanvasRef.value) return

  ctx.clearRect(0, 0, orbWidth, orbHeight)

  // Smoothly animate expansion when active
  const targetExpansion = props.isDebating ? 1.25 : 1.0
  currentExpansion += (targetExpansion - currentExpansion) * 0.05

  // Decide rotation speed based on state
  const speedMultiplier = props.isDebating ? 2.5 : 1
  globalRotationY += 0.002 * speedMultiplier
  globalRotationX += 0.0005 * speedMultiplier

  const frame: FrameState = {
    cx: orbWidth / 2,
    cy: orbHeight / 2,
    speedMultiplier,
    activeColorRGB: getRgbFromHex(props.activeAgentColor),
    currentAgentIndex: props.activeAgentIndex ?? 0
  }

  updateParticlePositions(speedMultiplier)
  drawConnections(ctx, frame)
  drawParticles(ctx, frame)
  drawAmbientDust(ctx, frame)

  animationFrameId = requestAnimationFrame(animateOrb)
}

// --- STT Logic ---
const isRecording = ref(false)
const mediaRecorder = ref<MediaRecorder | null>(null)
const audioChunks = ref<Blob[]>([])

const toggleRecording = async () => {
  if (isRecording.value) {
    mediaRecorder.value?.stop()
    isRecording.value = false
    store.isRecording = false
    stopSilenceDetection()
    return
  }

  try {
    store.stopTts() // Stop TTS when user wants to speak
    store.unlockAudioContext() // Unlock audio context and instantiate analyser during user click
    
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

// --- Silence Detection ---
let silenceTimeout: ReturnType<typeof setTimeout> | null = null
let initialDelayTimeout: ReturnType<typeof setTimeout> | null = null
let audioContext: AudioContext | null = null
let analyser: AnalyserNode | null = null
let microphone: MediaStreamAudioSourceNode | null = null
let silenceCheckInterval: ReturnType<typeof setInterval> | null = null

const startSilenceDetection = (stream: MediaStream) => {
  // Use a small delay before starting to avoid triggering on initial silence
  initialDelayTimeout = setTimeout(() => {
    if (!isRecording.value) return
    
    audioContext = new AudioContext()
    analyser = audioContext.createAnalyser()
    analyser.minDecibels = -70 // Sensitive threshold for voice
    analyser.smoothingTimeConstant = 0.2
    analyser.fftSize = 256 // good for time-domain waveform
    
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
      
      if (average > 3) { // User is talking
        if (silenceTimeout) {
          clearTimeout(silenceTimeout)
          silenceTimeout = null
        }
      } else if (!silenceTimeout) { // Silent
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

// --- Audio Waveform Visualizer ---
let waveOffset = 0
const animateWaveform = () => {
  if (!waveformCanvasRef.value) return
  const wCanvas = waveformCanvasRef.value
  const wCtx = wCanvas.getContext('2d')
  if (!wCtx) return

  wCtx.clearRect(0, 0, wCanvas.width, wCanvas.height)
  const width = wCanvas.width
  const height = wCanvas.height
  const centerY = height / 2

  let activeAnalyser: AnalyserNode | null = null
  let waveColor = '#ffffff'

  if (isRecording.value && analyser) {
    activeAnalyser = analyser
  } else if (store.isTtsPlaying && store.globalAnalyser) {
    activeAnalyser = store.globalAnalyser
    waveColor = props.activeAgentColor
  }

  if (activeAnalyser) {
    const dataArray = new Uint8Array(activeAnalyser.frequencyBinCount)
    activeAnalyser.getByteTimeDomainData(dataArray)
    
    wCtx.strokeStyle = waveColor
    wCtx.lineWidth = 2
    wCtx.beginPath()
    
    const sliceWidth = width * 1.0 / activeAnalyser.frequencyBinCount
    let x = 0
    
    for (let i = 0; i < activeAnalyser.frequencyBinCount; i++) {
      const v = dataArray[i]! / 128.0 // 0.0 to 2.0
      const y = (v * height) / 2
      
      if (i === 0) {
        wCtx.moveTo(x, y)
      } else {
        wCtx.lineTo(x, y)
      }
      x += sliceWidth
    }
    wCtx.stroke()
  } else {
    // Idle flat line / fake pulse
    wCtx.strokeStyle = 'rgba(255, 255, 255, 0.25)'
    wCtx.lineWidth = 1.2
    wCtx.beginPath()
    wCtx.moveTo(0, centerY)
    wCtx.lineTo(width, centerY)
    wCtx.stroke()

    const pulseX = (waveOffset * 30) % width
    wCtx.beginPath()
    wCtx.arc(pulseX, centerY, 1.8, 0, Math.PI * 2)
    wCtx.fillStyle = '#ffffff'
    wCtx.fill()

    waveOffset += 0.08
  }
  
  waveAnimationFrameId = requestAnimationFrame(animateWaveform)
}

onMounted(() => {
  resizeCanvas()
  initParticles()
  window.addEventListener('resize', resizeCanvas)
  animateOrb()
  animateWaveform()
})

onUnmounted(() => {
  isComponentUnmounted = true
  window.removeEventListener('resize', resizeCanvas)
  cancelAnimationFrame(animationFrameId)
  cancelAnimationFrame(waveAnimationFrameId)
  stopSilenceDetection()
  if (mediaRecorder.value && isRecording.value) {
    mediaRecorder.value.stop()
  }
})

watch(() => props.isDebating, () => {
  // Speed or parameters can be reset here if needed
})

watch(() => store.isWakeWordTriggered, (triggered) => {
  if (triggered && !isRecording.value) {
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
  return { backgroundColor: '#475569' } // slate-600
})
</script>

<template>
  <!-- CenterOrbCanvasCore -->
  <section class="flex flex-col relative w-full h-full border-x border-slate-800/80 overflow-hidden" data-purpose="neural-orb-centerpiece">
    
    <!-- Interactive Cosmic Neural Orb Web Canvas (Flex 1 ensures it takes remaining space, centering its content) -->
    <div class="relative w-full flex-1 flex items-center justify-center min-h-[300px] overflow-hidden" id="orbContainer">
      <!-- Sci-Fi Telemetry Orbit Rings & Coordinate Markings -->
      <div 
        class="absolute w-[440px] h-[440px] md:w-[580px] md:h-[580px] rounded-full border border-cyan-500/20 pointer-events-none animate-[spin_120s_linear_infinite]"
        :style="isDebating ? `border-color: ${activeAgentColor}40` : ''"
      ></div>
      <div 
        class="absolute w-[380px] h-[380px] md:w-[500px] md:h-[500px] rounded-full border border-dashed border-slate-700/40 pointer-events-none animate-[spin_80s_linear_infinite_reverse]"
        :style="isDebating ? `border-color: ${activeAgentColor}60` : ''"
      ></div>
      <div 
        class="absolute w-[470px] h-[470px] md:w-[620px] md:h-[620px] rounded-full border border-cyan-400/15 pointer-events-none"
        :style="isDebating ? `border-color: ${activeAgentColor}20` : ''"
      ></div>
      
      <!-- Central ambient luminous glow cores -->
      <div 
        class="absolute w-[380px] h-[380px] rounded-full blur-3xl pointer-events-none transition-colors duration-700"
        :style="isDebating ? `background-color: ${activeAgentColor}1A` : 'background-color: rgba(255, 255, 255, 0.05)'"
      ></div>
      <div 
        class="absolute w-[280px] h-[280px] rounded-full blur-2xl pointer-events-none transition-colors duration-700"
        :style="isDebating ? `background-color: ${activeAgentColor}33` : 'background-color: rgba(255, 255, 255, 0.1)'"
      ></div>

      <canvas ref="orbCanvasRef" class="w-full h-full absolute inset-0 z-10"></canvas>
    </div>

    <!-- Waveform Audio Visualizer, Voice State Controller & Microphone HUD Deck (Static/Mock for Phase 5) -->
    <div class="w-full bg-space-900/85 border-t border-slate-800/90 p-2.5 z-20 flex flex-col md:flex-row items-center justify-between gap-3 backdrop-blur-md shrink-0">
      <!-- Audio Deck Left: Microphone Button & Status Selector -->
      <div class="flex items-center space-x-3 w-full md:w-auto">
        <button id="micButton" 
          @click="toggleRecording"
          :class="isRecording ? 'border-red-500 bg-red-900/30' : 'border-slate-700 hover:border-cyan-400 bg-space-850 hover:bg-space-800'"
          class="relative group px-3 py-1.5 rounded-lg text-slate-300 hover:text-cyan-200 transition-all flex items-center space-x-2 shadow-md shrink-0 active:scale-95" 
          title="Activar micrófono para hablar (Pulsa para hablar)"
        >
          <div v-if="isRecording" class="absolute w-2 h-2 rounded-full bg-red-500 -top-1 -right-1 animate-pulse"></div>
          <div class="w-7 h-7 rounded-full bg-space-900 flex items-center justify-center border border-slate-700 group-hover:border-cyan-400" id="micIconRing">
            <svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-mic w-3.5 h-3.5 text-cyan-400 group-hover:scale-110 transition"><path d="M12 19v3"></path><path d="M19 10v2a7 7 0 0 1-14 0v-2"></path><rect x="9" y="2" width="6" height="13" rx="3"></rect></svg>
          </div>
          <div class="text-left font-mono">
            <div class="text-[10px] font-bold text-cyan-300 uppercase tracking-wider flex items-center gap-1">
              <span>MIC VOZ</span>
            </div>
            <div class="text-[8px] text-slate-400" id="micStatusSub">{{ isRecording ? 'ESCUCHANDO...' : 'LISTO PARA ESCUCHAR' }}</div>
          </div>
        </button>
      </div>

      <!-- Audio Spectrum Canvas Center -->
      <div class="flex items-center space-x-2 flex-1 max-w-sm w-full">
        <canvas ref="waveformCanvasRef" id="waveformCanvas" class="w-full h-8 rounded bg-space-950/70 border border-slate-800/80" width="280" height="32"></canvas>
      </div>

      <!-- Audio Status Caption Right -->
      <div class="w-full md:w-auto text-[10px] text-slate-400 font-mono flex items-center space-x-2 justify-end shrink-0">
        <span class="w-2 h-2 rounded-full transition-colors duration-300" id="voiceIndicatorDot" :style="voiceDotStyle"></span>
        <span class="text-slate-400 font-mono" id="voiceStateCaption">{{ voiceStateText }}</span>
      </div>
    </div>
    
  </section>
</template>
