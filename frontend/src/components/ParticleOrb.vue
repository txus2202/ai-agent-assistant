<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'

const props = defineProps<{
  activeAgentColor: string // e.g. '#00e5ff'
  isDebating: boolean
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
let ctx: CanvasRenderingContext2D | null = null
let animationFrameId: number

interface Particle {
  x: number; y: number; vx: number; vy: number; radius: number; life: number; maxLife: number
}

let particles: Particle[] = []

const initCanvas = () => {
  if (!canvasRef.value) return
  const canvas = canvasRef.value
  canvas.width = canvas.offsetWidth
  canvas.height = canvas.offsetHeight
  ctx = canvas.getContext('2d')
}

const createParticle = (x: number, y: number): Particle => {
  const angle = Math.random() * Math.PI * 2
  const speed = Math.random() * 2 + (props.isDebating ? 1 : 0.5)
  return {
    x, y,
    vx: Math.cos(angle) * speed,
    vy: Math.sin(angle) * speed,
    radius: Math.random() * 2 + 1,
    life: 0,
    maxLife: Math.random() * 50 + 50
  }
}

const animate = () => {
  if (!ctx || !canvasRef.value) return
  
  ctx.clearRect(0, 0, canvasRef.value.width, canvasRef.value.height)
  
  const centerX = canvasRef.value.width / 2
  const centerY = canvasRef.value.height / 2
  
  // Draw core orb
  const gradient = ctx.createRadialGradient(centerX, centerY, 10, centerX, centerY, 50)
  gradient.addColorStop(0, props.activeAgentColor)
  gradient.addColorStop(1, 'transparent')
  
  ctx.beginPath()
  ctx.arc(centerX, centerY, 50, 0, Math.PI * 2)
  ctx.fillStyle = gradient
  ctx.fill()
  
  // Particles
  if (props.isDebating && particles.length < 100) {
    for(let i=0; i<3; i++) particles.push(createParticle(centerX, centerY))
  }
  
  for (let i = particles.length - 1; i >= 0; i--) {
    const p = particles[i]
    p.x += p.vx
    p.y += p.vy
    p.life++
    
    if (p.life >= p.maxLife) {
      particles.splice(i, 1)
      continue
    }
    
    const alpha = 1 - (p.life / p.maxLife)
    ctx.beginPath()
    ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2)
    ctx.fillStyle = props.activeAgentColor.replace('rgb', 'rgba').replace(')', `, ${alpha})`).replace('#', '') // Simple fallback if hex
    
    // Hex to RGBA conversion for particles
    if (props.activeAgentColor.startsWith('#')) {
      const hex = props.activeAgentColor.replace('#', '')
      const r = parseInt(hex.substring(0, 2), 16)
      const g = parseInt(hex.substring(2, 4), 16)
      const b = parseInt(hex.substring(4, 6), 16)
      ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${alpha})`
    }
    
    ctx.fill()
  }
  
  animationFrameId = requestAnimationFrame(animate)
}

onMounted(() => {
  initCanvas()
  window.addEventListener('resize', initCanvas)
  animate()
})

onUnmounted(() => {
  window.removeEventListener('resize', initCanvas)
  cancelAnimationFrame(animationFrameId)
})

watch(() => props.activeAgentColor, () => {
  // Clear particles on color change for a cool effect
  particles = []
})
</script>

<template>
  <div class="relative w-full h-full min-h-[300px] flex items-center justify-center bg-space-950/50">
    <canvas ref="canvasRef" class="absolute inset-0 w-full h-full"></canvas>
    
    <!-- Pulse ring -->
    <div 
      v-if="isDebating"
      class="absolute w-24 h-24 rounded-full border border-current animate-ping opacity-20 pointer-events-none"
      :style="{ color: activeAgentColor }"
    ></div>
  </div>
</template>
