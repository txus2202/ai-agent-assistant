<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'
import SoundBar from './SoundBar.vue'

export interface ActiveAgentItem {
  role: string
  name?: string
  color: string
}

const props = withDefaults(defineProps<{
  activeAgentColor: string // e.g. '#00e5ff'
  isDebating: boolean
  activeAgentIndex?: number // Optional index (0 to 5) to identify the agent
  activeAgents?: ActiveAgentItem[]
}>(), {
  activeAgents: () => []
})

const resolvedActiveAgents = computed<ActiveAgentItem[]>(() => {
  if (!props.isDebating) {
    return []
  }
  if (props.activeAgents && props.activeAgents.length > 0) {
    return props.activeAgents
  }
  if (props.activeAgentColor) {
    return [{ role: 'active', color: props.activeAgentColor }]
  }
  return []
})

const emit = defineEmits<{
  (e: 'submit-draft'): void
}>()

const orbCanvasRef = ref<HTMLCanvasElement | null>(null)
const soundBarRef = ref<InstanceType<typeof SoundBar> | null>(null)
let ctx: CanvasRenderingContext2D | null = null
let animationFrameId: number
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
  const fallbackW = typeof window !== 'undefined' ? window.innerWidth : 800
  const fallbackH = typeof window !== 'undefined' && window.innerHeight ? window.innerHeight - 112 : 560
  orbWidth = canvas.width = (rect && rect.width > 50) ? Math.floor(rect.width) : fallbackW
  orbHeight = canvas.height = (rect && rect.height > 50) ? Math.floor(rect.height) : fallbackH
  const minDimension = Math.min(orbWidth, orbHeight)
  BASE_RADIUS = minDimension < 460
    ? Math.max(105, minDimension * 0.36)
    : Math.max(180, Math.min(235, minDimension * 0.38))
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
const getIdleParticleRgb = (groupId?: number) => {
  if (typeof document !== 'undefined' && document.documentElement.classList.contains('light')) {
    // Crisp constellation ink dots in light mode, with subtle teal accents
    return (groupId !== undefined && groupId % 2 === 0) ? '15, 118, 110' : '15, 23, 42'
  }
  return '255, 255, 255'
}

interface AgentRgbItem {
  role: string
  hex: string
  rgb: string
}

interface FrameState {
  cx: number
  cy: number
  speedMultiplier: number
  activeColorRGB: string
  currentAgentIndex: number
  activeAgentsRgb: AgentRgbItem[]
}

const project = (z: number) => 800 / (800 + z)

const getParticleActiveAgent = (
  p: Particle3D,
  frame: FrameState
): { isActive: boolean; rgb: string; hex: string } => {
  const agents = frame.activeAgentsRgb
  if (!props.isDebating || agents.length === 0) {
    return { isActive: false, rgb: getIdleParticleRgb(p.groupId), hex: '' }
  }

  // Case 1: Single agent active (alternating plexus or index)
  if (agents.length === 1) {
    const a = agents[0]!
    const isActive = p.groupId % 2 === 0 || p.groupId === (props.activeAgentIndex ?? 0)
    return {
      isActive,
      rgb: isActive ? a.rgb : getIdleParticleRgb(p.groupId),
      hex: a.hex
    }
  }

  // Case 2: 2 agents in parallel (Bipolar hemispheres: Left vs Right + equator data crossover)
  if (agents.length === 2) {
    const a1 = agents[0]!
    const a2 = agents[1]!
    let chosen: AgentRgbItem
    if (p.ox < -0.04) {
      chosen = a1
    } else if (p.ox > 0.04) {
      chosen = a2
    } else {
      chosen = p.oz > 0 ? a1 : a2
    }
    return { isActive: true, rgb: chosen.rgb, hex: chosen.hex }
  }

  // Case 3+: 3 or more agents in parallel (Equidistant angular meridian sectors around the orb)
  const count = agents.length
  const angle = Math.atan2(p.oz, p.ox)
  const normAngle = ((angle + Math.PI) / (2 * Math.PI) + 1) % 1
  const sector = Math.floor(normAngle * count) % count
  const chosen = agents[sector]!
  return { isActive: true, rgb: chosen.rgb, hex: chosen.hex }
}

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
  c: CanvasRenderingContext2D,
  p1: Particle3D,
  p2: Particle3D,
  distSq: number,
  rgb1: string,
  rgb2: string,
  isActive1: boolean,
  isActive2: boolean,
  frame: FrameState
) => {
  const persp1 = project(p1.z)
  const persp2 = project(p2.z)
  const isLight = typeof document !== 'undefined' && document.documentElement.classList.contains('light')
  const alphaMultiplier = isLight ? 0.35 : 0.3
  const isBothActive = isActive1 && isActive2
  const isSameAgent = rgb1 === rgb2

  let strokeColor = rgb1
  if ((!isActive1 && !isActive2) || (isBothActive && !isSameAgent)) {
    // Idle links or inter-agent crossover confluence link
    strokeColor = isLight ? '15, 23, 42' : '255, 255, 255'
  }

  let linkAlphaFactor = 0.3
  if (isBothActive) {
    linkAlphaFactor = 0.85
  } else if (isLight) {
    linkAlphaFactor = 0.45
  }
  const alpha = (1 - Math.sqrt(distSq) / 50) * alphaMultiplier * linkAlphaFactor
  c.beginPath()
  c.moveTo(frame.cx + p1.x * persp1, frame.cy + p1.y * persp1)
  c.lineTo(frame.cx + p2.x * persp2, frame.cy + p2.y * persp2)
  c.strokeStyle = `rgba(${strokeColor}, ${alpha})`
  c.stroke()
}

const drawConnectionsFor = (
  c: CanvasRenderingContext2D, i: number, frame: FrameState
) => {
  const p1 = particles[i]!
  const a1 = getParticleActiveAgent(p1, frame)

  // Only check connections for a subset to save performance
  for (let j = i + 1; j < particles.length; j += 2) {
    const p2 = particles[j]!
    if (p2.z < FAR_Z) continue
    const dx = p1.x - p2.x
    const dy = p1.y - p2.y
    const dz = p1.z - p2.z
    const distSq = dx * dx + dy * dy + dz * dz
    if (distSq < 2500) {
      const a2 = getParticleActiveAgent(p2, frame)
      drawLink(c, p1, p2, distSq, a1.rgb, a2.rgb, a1.isActive, a2.isActive, frame)
    }
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
  const agentInfo = getParticleActiveAgent(p, frame)
  const isActive = agentInfo.isActive
  const baseColor = agentInfo.rgb

  const projSize = (isActive ? p.size * 1.5 : p.size) * perspective
  const depthAlpha = Math.max(0.08, Math.min(1, (p.z + BASE_RADIUS) / (BASE_RADIUS * 2.5)))
  const isLight = typeof document !== 'undefined' && document.documentElement.classList.contains('light')
  let finalAlpha: number
  if (isActive) {
    finalAlpha = Math.min(1, p.alpha * depthAlpha * 2.2)
  } else if (isLight) {
    finalAlpha = Math.min(0.95, p.alpha * depthAlpha * 1.6 + 0.35)
  } else {
    finalAlpha = p.alpha * depthAlpha
  }

  c.beginPath()
  c.arc(px, py, projSize, 0, Math.PI * 2)
  c.fillStyle = `rgba(${baseColor}, ${finalAlpha})`
  c.fill()

  if (!isActive) return
  // Subtle glow for active particles
  c.beginPath()
  c.arc(px, py, projSize * 3, 0, Math.PI * 2)
  c.fillStyle = `rgba(${baseColor}, ${finalAlpha * 0.22})`
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

const getAmbientDustColor = (isDebating: boolean, isLight: boolean, primaryColor: string) => {
  if (isDebating) {
    return primaryColor
  }
  if (isLight) {
    return '15, 23, 42'
  }
  return '255, 255, 255'
}

const drawAmbientDust = (c: CanvasRenderingContext2D, frame: FrameState) => {
  const isLight = typeof document !== 'undefined' && document.documentElement.classList.contains('light')
  const primaryColor = frame.activeAgentsRgb.length > 0 ? frame.activeAgentsRgb[0]!.rgb : frame.activeColorRGB
  const color = getAmbientDustColor(props.isDebating, isLight, primaryColor)
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
  if (isComponentUnmounted || !ctx || !orbCanvasRef.value) return

  ctx.clearRect(0, 0, orbWidth, orbHeight)

  // Smoothly animate expansion when active
  const targetExpansion = props.isDebating ? 1.25 : 1.0
  currentExpansion += (targetExpansion - currentExpansion) * 0.05

  // Decide rotation speed based on state
  const speedMultiplier = props.isDebating ? 2.5 : 1
  globalRotationY += 0.002 * speedMultiplier
  globalRotationX += 0.0005 * speedMultiplier

  const agents = resolvedActiveAgents.value
  const activeAgentsRgb: AgentRgbItem[] = agents.map(a => ({
    role: a.role,
    hex: a.color,
    rgb: getRgbFromHex(a.color)
  }))

  const frame: FrameState = {
    cx: orbWidth / 2,
    cy: orbHeight / 2,
    speedMultiplier,
    activeColorRGB: getRgbFromHex(props.activeAgentColor),
    currentAgentIndex: props.activeAgentIndex ?? 0,
    activeAgentsRgb
  }

  updateParticlePositions(speedMultiplier)
  drawConnections(ctx, frame)
  drawParticles(ctx, frame)
  drawAmbientDust(ctx, frame)

  animationFrameId = requestAnimationFrame(animateOrb)
}

let resizeObserver: ResizeObserver | null = null

onMounted(() => {
  resizeCanvas()
  initParticles()
  window.addEventListener('resize', resizeCanvas)
  if (typeof ResizeObserver !== 'undefined' && orbCanvasRef.value?.parentElement) {
    resizeObserver = new ResizeObserver(() => {
      resizeCanvas()
    })
    resizeObserver.observe(orbCanvasRef.value.parentElement)
  }
  animateOrb()
})

onUnmounted(() => {
  isComponentUnmounted = true
  window.removeEventListener('resize', resizeCanvas)
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
  cancelAnimationFrame(animationFrameId)
})

const toggleRecording = () => {
  return soundBarRef.value?.toggleRecording()
}

defineExpose({
  toggleRecording,
  resizeCanvas
})

watch(() => props.isDebating, () => {
  // Speed or parameters can be reset here if needed
})

const coreGlowStyle1 = computed(() => {
  if (!props.isDebating) return {}
  const agents = resolvedActiveAgents.value
  if (agents.length === 0) return {}
  if (agents.length === 1) {
    return { backgroundColor: `${agents[0]!.color}26` }
  }
  if (agents.length === 2) {
    return { 
      background: `radial-gradient(circle at center, ${agents[0]!.color}26 0%, ${agents[1]!.color}26 60%, transparent 75%)` 
    }
  }
  const step = 360 / agents.length
  const stops = agents.map((a, i) => `${a.color}33 ${Math.round(i * step)}deg, ${a.color}33 ${Math.round((i + 1) * step)}deg`).join(', ')
  return {
    background: `conic-gradient(from 0deg at 50% 50%, ${stops})`
  }
})

const coreGlowStyle2 = computed(() => {
  if (!props.isDebating) return {}
  const agents = resolvedActiveAgents.value
  if (agents.length === 0) return {}
  if (agents.length === 1) {
    return { backgroundColor: `${agents[0]!.color}40` }
  }
  if (agents.length === 2) {
    return { 
      background: `radial-gradient(circle at center, ${agents[1]!.color}33 0%, ${agents[0]!.color}33 60%, transparent 75%)` 
    }
  }
  const step = 360 / agents.length
  const stops = agents.map((a, i) => `${a.color}26 ${Math.round((i + 0.5) * step)}deg, ${a.color}26 ${Math.round((i + 1.5) * step)}deg`).join(', ')
  return {
    background: `conic-gradient(from 180deg at 50% 50%, ${stops})`
  }
})

const ring1Style = computed(() => {
  if (!props.isDebating) return ''
  const agents = resolvedActiveAgents.value
  const color = agents.length > 0 ? agents[0]!.color : props.activeAgentColor
  return `border-color: ${color}40`
})

const ring2Style = computed(() => {
  if (!props.isDebating) return ''
  const agents = resolvedActiveAgents.value
  const targetAgent = agents[1] || agents[0]
  const color = targetAgent ? targetAgent.color : props.activeAgentColor
  return `border-color: ${color}60`
})

const ring3Style = computed(() => {
  if (!props.isDebating) return ''
  const agents = resolvedActiveAgents.value
  const targetAgent = agents[2] || agents[0]
  const color = targetAgent ? targetAgent.color : props.activeAgentColor
  return `border-color: ${color}20`
})
</script>

<template>
  <!-- CenterOrbCanvasCore -->
  <section class="flex flex-col relative w-full h-full border-x border-slate-800/80 overflow-hidden" data-purpose="neural-orb-centerpiece">
    
    <!-- Waveform Audio Visualizer, Voice State Controller & Microphone HUD Deck via SoundBar (Floating Top on Mobile, Bottom Dock on Tablet/Desktop) -->
    <div class="order-1 md:order-2 w-full bg-space-900/85 border-b md:border-b-0 md:border-t border-slate-800/90 px-4 sm:px-6 py-2.5 z-20 backdrop-blur-md shrink-0 absolute top-0 left-0 md:relative">
      <SoundBar
        ref="soundBarRef"
        :active-agent-color="activeAgentColor"
        :is-debating="isDebating"
        :listen-wake-word="true"
        @submit-draft="emit('submit-draft')"
      />
    </div>

    <!-- Interactive Cosmic Neural Orb Web Canvas (Centered in screen on mobile, flex-1 min-h-0 on tablet/desktop) -->
    <div class="order-2 md:order-1 relative w-full h-full flex-1 flex items-center justify-center min-h-0 xl:min-h-[300px] overflow-hidden" id="orbContainer">
      <!-- Sci-Fi Telemetry Orbit Rings & Coordinate Markings -->
      <div 
        id="orbRing1"
        class="absolute w-[280px] h-[280px] sm:w-[440px] sm:h-[440px] xl:w-[580px] xl:h-[580px] rounded-full border border-cyan-500/20 pointer-events-none animate-[spin_120s_linear_infinite]"
        :style="ring1Style"
      ></div>
      <div 
        id="orbRing2"
        class="absolute w-[240px] h-[240px] sm:w-[380px] sm:h-[380px] xl:w-[500px] xl:h-[500px] rounded-full border border-dashed border-slate-700/40 pointer-events-none animate-[spin_80s_linear_infinite_reverse]"
        :style="ring2Style"
      ></div>
      <div 
        id="orbRing3"
        class="absolute w-[310px] h-[310px] sm:w-[470px] sm:h-[470px] xl:w-[620px] xl:h-[620px] rounded-full border border-cyan-400/15 pointer-events-none"
        :style="ring3Style"
      ></div>
      
      <!-- Central ambient luminous glow cores -->
      <div 
        id="orbGlowCore1"
        class="absolute w-[260px] h-[260px] sm:w-[380px] sm:h-[380px] rounded-full blur-3xl pointer-events-none transition-colors duration-700"
        :style="coreGlowStyle1"
      ></div>
      <div 
        id="orbGlowCore2"
        class="absolute w-[200px] h-[200px] sm:w-[280px] sm:h-[280px] rounded-full blur-2xl pointer-events-none transition-colors duration-700"
        :style="coreGlowStyle2"
      ></div>

      <canvas ref="orbCanvasRef" class="w-full h-full absolute inset-0 z-10"></canvas>
    </div>
    
  </section>
</template>
