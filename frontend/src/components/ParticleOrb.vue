<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'

const props = defineProps<{
  activeAgentColor: string // e.g. '#00e5ff'
  isDebating: boolean
  activeAgentIndex?: number // Optional index (0 to 5) to identify the agent
}>()

const orbCanvasRef = ref<HTMLCanvasElement | null>(null)
const waveformCanvasRef = ref<HTMLCanvasElement | null>(null)
let ctx: CanvasRenderingContext2D | null = null
let animationFrameId: number
let waveAnimationFrameId: number

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
const ambientDust: any[] = []
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
    const radOffset = (Math.random() - 0.45) * 36

    particles.push({
      ox: xNorm, oy: yNorm, oz: zNorm,
      x: 0, y: 0, z: 0,
      size: Math.random() * 1.5 + 0.8, // Slightly larger particles
      alpha: Math.random() * 0.5 + 0.3,
      linkDistance: 1 + radOffset / BASE_RADIUS,
      phase: Math.random() * Math.PI * 2,
      groupId: i % TOTAL_AGENTS // Divide particles equally among agents
    })
  }

  for (let i = 0; i < AMBIENT_DUST_COUNT; i++) {
    ambientDust.push({
      x: (Math.random() - 0.5) * orbWidth * 1.5,
      y: (Math.random() - 0.5) * orbHeight * 1.5,
      z: (Math.random() - 0.5) * 800,
      size: Math.random() * 2,
      vx: (Math.random() - 0.5) * 0.4,
      vy: (Math.random() - 0.5) * 0.4,
      vz: (Math.random() - 0.5) * 0.4
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
  const r = parseInt(c.substring(0, 2), 16)
  const g = parseInt(c.substring(2, 4), 16)
  const b = parseInt(c.substring(4, 6), 16)
  return `${isNaN(r) ? 255 : r}, ${isNaN(g) ? 255 : g}, ${isNaN(b) ? 255 : b}`
}

let currentExpansion = 1.0

const animateOrb = () => {
  if (!ctx || !orbCanvasRef.value) return
  
  ctx.clearRect(0, 0, orbWidth, orbHeight)
  const cx = orbWidth / 2
  const cy = orbHeight / 2
  
  // Smoothly animate expansion when active
  const targetExpansion = props.isDebating ? 1.25 : 1.0
  currentExpansion += (targetExpansion - currentExpansion) * 0.05
  
  // Decide rotation speed based on state
  const speedMultiplier = props.isDebating ? 2.5 : 1
  globalRotationY += 0.002 * speedMultiplier
  globalRotationX += 0.0005 * speedMultiplier
  
  const cosY = Math.cos(globalRotationY)
  const sinY = Math.sin(globalRotationY)
  const cosX = Math.cos(globalRotationX)
  const sinX = Math.sin(globalRotationX)
  
  const activeColorRGB = getRgbFromHex(props.activeAgentColor)
  const currentAgentIndex = props.activeAgentIndex !== undefined ? props.activeAgentIndex : 0

  // Calculate 3D positions
  particles.forEach(p => {
    let rx1 = p.ox * cosY - p.oz * sinY
    let rz1 = p.oz * cosY + p.ox * sinY
    let ry1 = p.oy * cosX - rz1 * sinX
    let rz2 = rz1 * cosX + p.oy * sinX
    
    p.phase += 0.02 * speedMultiplier
    const currentRadius = (BASE_RADIUS * p.linkDistance + Math.sin(p.phase) * 5) * currentExpansion
    
    p.x = rx1 * currentRadius
    p.y = ry1 * currentRadius
    p.z = rz2 * currentRadius
  })

  // Draw Plexus Connections
  ctx!.lineWidth = 0.5
  for (let i = 0; i < particles.length; i++) {
    const p1 = particles[i]
    if (p1.z < -700) continue // Skip far particles for performance
    
    // Determine color based on active state and group
    const isActiveParticle = props.isDebating && p1.groupId === currentAgentIndex
    const p1Color = isActiveParticle ? activeColorRGB : '255, 255, 255'
    
    // Only check connections for a subset to save performance
    for (let j = i + 1; j < particles.length; j += 2) {
      const p2 = particles[j]
      if (p2.z < -700) continue
      
      const dx = p1.x - p2.x
      const dy = p1.y - p2.y
      const dz = p1.z - p2.z
      const distSq = dx*dx + dy*dy + dz*dz
      
      if (distSq < 2500) { // Connect if distance is less than 50
        const perspective1 = 800 / (800 + p1.z)
        const perspective2 = 800 / (800 + p2.z)
        
        const px1 = cx + p1.x * perspective1
        const py1 = cy + p1.y * perspective1
        const px2 = cx + p2.x * perspective2
        const py2 = cy + p2.y * perspective2
        
        const alpha = (1 - Math.sqrt(distSq) / 50) * 0.3 * (isActiveParticle ? 0.8 : 0.3)
        ctx!.beginPath()
        ctx!.moveTo(px1, py1)
        ctx!.lineTo(px2, py2)
        ctx!.strokeStyle = `rgba(${p1Color}, ${alpha})`
        ctx!.stroke()
      }
    }
  }

  // Draw Particles
  particles.forEach(p => {
    if (p.z > -700) {
      const perspective = 800 / (800 + p.z)
      const px = cx + p.x * perspective
      const py = cy + p.y * perspective
      
      const isActiveParticle = props.isDebating && p.groupId === currentAgentIndex
      const baseColor = isActiveParticle ? activeColorRGB : '255, 255, 255'
      
      // Make active particles slightly larger and brighter
      const projSize = (isActiveParticle ? p.size * 1.5 : p.size) * perspective
      const depthAlpha = Math.max(0.05, Math.min(1, (p.z + BASE_RADIUS) / (BASE_RADIUS * 2.5)))
      const finalAlpha = isActiveParticle ? Math.min(1, p.alpha * depthAlpha * 2) : p.alpha * depthAlpha
      
      ctx!.beginPath()
      ctx!.arc(px, py, projSize, 0, Math.PI * 2)
      ctx!.fillStyle = `rgba(${baseColor}, ${finalAlpha})`
      ctx!.fill()
      
      // Add subtle glow to active particles
      if (isActiveParticle) {
        ctx!.beginPath()
        ctx!.arc(px, py, projSize * 3, 0, Math.PI * 2)
        ctx!.fillStyle = `rgba(${baseColor}, ${finalAlpha * 0.2})`
        ctx!.fill()
      }
    }
  })

  // Draw Ambient dust
  const globalBaseColor = props.isDebating ? activeColorRGB : '255, 255, 255'
  ambientDust.forEach(d => {
    d.x += d.vx * speedMultiplier
    d.y += d.vy * speedMultiplier
    d.z += d.vz * speedMultiplier
    
    if (d.x > orbWidth) d.x = -orbWidth
    if (d.x < -orbWidth) d.x = orbWidth
    if (d.y > orbHeight) d.y = -orbHeight
    if (d.y < -orbHeight) d.y = orbHeight
    
    const perspective = 800 / (800 + d.z)
    const px = cx + d.x * perspective
    const py = cy + d.y * perspective
    
    if (d.z > -700) {
      ctx!.beginPath()
      ctx!.arc(px, py, d.size * perspective, 0, Math.PI * 2)
      ctx!.fillStyle = `rgba(${globalBaseColor}, ${0.1 * perspective})`
      ctx!.fill()
    }
  })

  animationFrameId = requestAnimationFrame(animateOrb)
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
  window.removeEventListener('resize', resizeCanvas)
  cancelAnimationFrame(animationFrameId)
  cancelAnimationFrame(waveAnimationFrameId)
})

watch(() => props.isDebating, () => {
  // Speed or parameters can be reset here if needed
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
        <button id="micButton" class="relative group px-3 py-1.5 rounded-lg bg-space-850 hover:bg-space-800 border border-slate-700 hover:border-cyan-400 text-slate-300 hover:text-cyan-200 transition-all flex items-center space-x-2 shadow-md shrink-0 active:scale-95" title="Activar micrófono para hablar (Pulsa para hablar)">
          <div class="w-7 h-7 rounded-full bg-space-900 flex items-center justify-center border border-slate-700 group-hover:border-cyan-400" id="micIconRing">
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-mic w-3.5 h-3.5 text-cyan-400 group-hover:scale-110 transition"><path d="M12 19v3"></path><path d="M19 10v2a7 7 0 0 1-14 0v-2"></path><rect x="9" y="2" width="6" height="13" rx="3"></rect></svg>
          </div>
          <div class="text-left font-mono">
            <div class="text-[10px] font-bold text-cyan-300 uppercase tracking-wider flex items-center gap-1">
              <span>MIC VOZ</span>
            </div>
            <div class="text-[8px] text-slate-400" id="micStatusSub">LISTO PARA ESCUCHAR</div>
          </div>
        </button>
      </div>

      <!-- Audio Spectrum Canvas Center -->
      <div class="flex items-center space-x-2 flex-1 max-w-sm w-full">
        <canvas ref="waveformCanvasRef" id="waveformCanvas" class="w-full h-8 rounded bg-space-950/70 border border-slate-800/80" width="280" height="32"></canvas>
      </div>

      <!-- Audio Status Caption Right -->
      <div class="w-full md:w-auto text-[10px] text-slate-400 font-mono flex items-center space-x-2 justify-end shrink-0">
        <span class="w-2 h-2 rounded-full bg-slate-600" id="voiceIndicatorDot"></span>
        <span class="text-slate-400 font-mono" id="voiceStateCaption">ESTADO VOZ: EN REPOSO</span>
      </div>
    </div>
    
  </section>
</template>
