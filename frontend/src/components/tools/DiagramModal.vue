<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { Copy, Check, X, ZoomIn, ZoomOut, RotateCcw, Network, Download } from '@lucide/vue'
import mermaid from 'mermaid'

const props = withDefaults(
  defineProps<{
    isOpen: boolean
    code: string
    title?: string
    teleportDisabled?: boolean
  }>(),
  {
    title: 'Diagrama de Arquitectura',
    teleportDisabled: false
  }
)

const isTestEnv = import.meta !== undefined && import.meta.env?.MODE === 'test'
const shouldDisableTeleport = computed(() => props.teleportDisabled || isTestEnv)

const emit = defineEmits<{
  (e: 'close'): void
}>()

const isCopied = ref(false)
const zoomLevel = ref(1)
const diagramSvg = ref<string>('')
const renderError = ref<string | null>(null)
const diagramContainerRef = ref<HTMLElement | null>(null)

// Initialize Mermaid with dark theme
try {
  mermaid.initialize({
    startOnLoad: false,
    theme: 'dark',
    securityLevel: 'loose',
    fontFamily: 'monospace, sans-serif',
    flowchart: {
      useMaxWidth: false,
      htmlLabels: true
    },
    sequence: {
      useMaxWidth: false
    },
    gantt: {
      useMaxWidth: false
    },
    journey: {
      useMaxWidth: false
    }
  })
} catch (e) {
  console.warn('Mermaid initialization warning:', e)
}

const renderDiagram = async () => {
  if (!props.isOpen || !props.code) return

  renderError.value = null
  diagramSvg.value = ''

  await nextTick()

  const id = `mermaid-modal-${Date.now()}-${Math.floor(Math.random() * 10000)}`
  try {
    const { svg } = await mermaid.render(id, props.code)
    // Remove rigid inline max-width from SVG so it scales fluidly and never clips
    diagramSvg.value = svg.replace(/max-width:\s*[\d.]+px;?/gi, '')
  } catch (err: unknown) {
    console.error('Error rendering Mermaid diagram:', err)
    renderError.value = err instanceof Error ? err.message : 'Error de sintaxis en el diagrama'
  }
}

watch(
  () => [props.isOpen, props.code],
  async ([newOpen]) => {
    if (newOpen) {
      zoomLevel.value = 1
      await renderDiagram()
    }
  },
  { immediate: true }
)

const copyCode = async () => {
  if (!props.code) return
  try {
    await navigator.clipboard.writeText(props.code)
    isCopied.value = true
    setTimeout(() => {
      isCopied.value = false
    }, 2000)
  } catch (err) {
    console.error('Failed to copy to clipboard:', err)
  }
}

const downloadSvg = () => {
  if (!diagramSvg.value) return
  try {
    const safeTitle = (props.title || 'diagrama')
      .toLowerCase()
      .replace(/[^a-z0-9_-]+/g, '_')
      .slice(0, 30)
    const blob = new Blob([diagramSvg.value], { type: 'image/svg+xml;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${safeTitle}_${Date.now()}.svg`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  } catch (err) {
    console.error('Failed to download SVG diagram:', err)
  }
}

const zoomIn = () => {
  if (zoomLevel.value < 2.5) {
    zoomLevel.value = Math.round((zoomLevel.value + 0.1) * 10) / 10
  }
}

const zoomOut = () => {
  if (zoomLevel.value > 0.5) {
    zoomLevel.value = Math.round((zoomLevel.value - 0.1) * 10) / 10
  }
}

const resetZoom = () => {
  zoomLevel.value = 1
}

const handleKeyDown = (event: KeyboardEvent) => {
  if (event.key === 'Escape' && props.isOpen) {
    emit('close')
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeyDown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
})
</script>

<template>
  <Teleport to="body" :disabled="shouldDisableTeleport">
    <dialog
      v-if="isOpen"
      open
      data-test="diagram-modal-backdrop"
      class="fixed inset-0 z-[99999] bg-black/85 backdrop-blur-md flex flex-col items-center justify-center p-2 sm:p-4 md:p-8 pt-[max(0.75rem,env(safe-area-inset-top))] pb-[max(0.75rem,env(safe-area-inset-bottom))] animate-fade-in border-0 m-0 w-full h-full max-w-none max-h-none text-inherit"
      @click.self="emit('close')"
      @cancel.prevent="emit('close')"
      @keydown="handleKeyDown"
      aria-labelledby="diagram-modal-title"
      aria-modal="true"
    >
      <!-- Modal Window -->
      <div
        class="w-full max-w-6xl h-[94vh] sm:h-[88vh] max-h-[100dvh] bg-[#060a11] border border-cyan-500/40 rounded-xl sm:rounded-2xl shadow-[0_0_50px_rgba(0,229,255,0.2)] flex flex-col overflow-hidden m-auto"
      >
        <!-- Modal Header -->
        <div
          class="flex items-center justify-between px-3 sm:px-6 py-2.5 sm:py-4 border-b border-space-800 bg-[#080d1a] gap-2 min-w-0"
        >
          <!-- Left branding: Icon - Herramienta -->
          <div class="flex items-center gap-2 sm:gap-2.5 shrink-0">
            <div
              class="w-7 h-7 sm:w-8 sm:h-8 rounded-lg bg-neon-cyan/10 border border-neon-cyan/40 flex items-center justify-center text-neon-cyan shadow-[0_0_10px_rgba(0,229,255,0.2)] shrink-0"
            >
              <Network class="w-3.5 h-3.5 sm:w-4 sm:h-4" />
            </div>
            <h3
              id="diagram-modal-title"
              class="text-xs sm:text-sm font-mono font-bold text-neon-cyan tracking-wider uppercase select-none"
            >
              Diagrama
            </h3>
          </div>

          <!-- Controls Toolbar -->
          <div class="flex items-center gap-1 sm:gap-2 shrink-0">
            <!-- Zoom Controls -->
            <div
              class="flex items-center bg-[#030509] border border-space-700 rounded-lg px-1 sm:px-2 py-0.5 sm:py-1 gap-1 sm:gap-2 font-mono text-xs text-slate-300"
            >
              <button
                type="button"
                @click="zoomOut"
                data-test="zoom-out-btn"
                class="p-1 hover:text-neon-cyan transition-colors"
                title="Reducir zoom"
                aria-label="Reducir zoom"
              >
                <ZoomOut class="w-3.5 h-3.5" />
              </button>
              <span
                data-test="zoom-level-text"
                class="text-[10px] sm:text-[11px] w-8 sm:w-11 text-center text-neon-cyan font-bold select-none"
              >
                {{ Math.round(zoomLevel * 100) }}%
              </span>
              <button
                type="button"
                @click="zoomIn"
                data-test="zoom-in-btn"
                class="p-1 hover:text-neon-cyan transition-colors"
                title="Aumentar zoom"
                aria-label="Aumentar zoom"
              >
                <ZoomIn class="w-3.5 h-3.5" />
              </button>
              <button
                type="button"
                @click="resetZoom"
                data-test="zoom-reset-btn"
                class="p-1 hover:text-neon-cyan border-l border-space-800 pl-1.5 sm:pl-2 transition-colors"
                title="Restablecer tamaño"
                aria-label="Restablecer tamaño"
              >
                <RotateCcw class="w-3.5 h-3.5" />
              </button>
            </div>

            <!-- Copy Button -->
            <button
              type="button"
              @click="copyCode"
              data-test="diagram-modal-copy-btn"
              class="relative group p-1.5 sm:p-2 rounded-lg border transition-all cursor-pointer flex items-center justify-center shrink-0"
              :class="
                isCopied
                  ? 'bg-emerald-500/20 border-emerald-500/60 text-emerald-300'
                  : 'bg-[#030509] border-cyan-500/40 hover:border-neon-cyan text-cyan-200 hover:text-white'
              "
              :title="isCopied ? 'Copiado al portapapeles' : 'Copiar código al portapapeles'"
              :aria-label="isCopied ? 'Copiado al portapapeles' : 'Copiar código al portapapeles'"
            >
              <Check v-if="isCopied" class="w-3.5 h-3.5 sm:w-4 sm:h-4 text-emerald-400" />
              <Copy v-else class="w-3.5 h-3.5 sm:w-4 sm:h-4" />
              <!-- Hover Tooltip -->
              <span
                class="pointer-events-none absolute top-full mt-2 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono text-cyan-200 border border-cyan-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
              >
                {{ isCopied ? 'Copiado' : 'Copiar' }}
              </span>
            </button>

            <!-- Download SVG Button -->
            <button
              type="button"
              @click="downloadSvg"
              data-test="diagram-modal-download-btn"
              class="relative group p-1.5 sm:p-2 rounded-lg bg-neon-cyan/15 hover:bg-neon-cyan/25 border border-neon-cyan text-neon-cyan transition-colors cursor-pointer flex items-center justify-center shrink-0"
              title="Descargar diagrama en formato SVG"
              aria-label="Descargar diagrama en formato SVG"
            >
              <Download class="w-3.5 h-3.5 sm:w-4 sm:h-4" />
              <!-- Hover Tooltip -->
              <span
                class="pointer-events-none absolute top-full mt-2 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono font-bold text-neon-cyan border border-neon-cyan/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
              >
                Descargar SVG
              </span>
            </button>

            <!-- Close Button -->
            <button
              type="button"
              @click="emit('close')"
              data-test="diagram-modal-close-btn"
              class="relative group p-1.5 sm:p-2 rounded-lg bg-[#030509] border border-space-700 hover:border-red-500/50 hover:bg-red-950/30 text-slate-400 hover:text-red-400 transition-colors ml-0.5 sm:ml-1 cursor-pointer flex items-center justify-center shrink-0"
              title="Cerrar (Esc)"
              aria-label="Cerrar"
            >
              <X class="w-3.5 h-3.5 sm:w-4 sm:h-4" />
              <!-- Hover Tooltip -->
              <span
                class="pointer-events-none absolute top-full mt-2 right-0 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono text-slate-300 border border-space-700 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
              >
                Cerrar (Esc)
              </span>
            </button>
          </div>
        </div>

        <!-- Diagram Canvas Content -->
        <div
          ref="diagramContainerRef"
          class="flex-1 overflow-auto bg-[#020408] relative custom-scrollbar select-none"
        >
          <div class="min-w-full min-h-full flex items-center justify-center p-3 sm:p-6 md:p-8 m-auto">
            <!-- Error State -->
            <div
              v-if="renderError"
              class="max-w-xl p-6 bg-red-950/20 border border-red-500/40 rounded-xl text-center font-mono m-auto"
            >
              <div class="text-red-400 text-sm font-bold mb-2">Error al renderizar el diagrama</div>
              <div class="text-xs text-slate-400 mb-4">{{ renderError }}</div>
              <pre
                class="p-3 bg-[#030509] border border-space-800 rounded text-left text-xs text-cyan-300 overflow-x-auto"
                >{{ code }}</pre
              >
            </div>

            <!-- Rendered Diagram SVG with Scaled Transform -->
            <div
              v-else-if="diagramSvg"
              data-test="rendered-diagram-svg"
              class="diagram-svg-wrapper transition-transform duration-200 ease-out origin-center flex items-center justify-center m-auto"
              :style="{ transform: `scale(${zoomLevel})` }"
              v-html="diagramSvg"
            ></div>

            <!-- Loading State -->
            <div v-else class="flex flex-col items-center gap-3 text-neon-cyan font-mono text-xs m-auto">
              <div class="w-6 h-6 border-2 border-neon-cyan border-t-transparent rounded-full animate-spin"></div>
              <span>Generando representación visual...</span>
            </div>
          </div>
        </div>
      </div>
    </dialog>
  </Teleport>
</template>

<style scoped>
.diagram-svg-wrapper {
  max-width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.diagram-svg-wrapper :deep(svg) {
  display: block;
  margin: auto;
  max-width: 100%;
  max-height: 72vh;
  width: auto;
  height: auto;
  overflow: visible;
}
</style>

