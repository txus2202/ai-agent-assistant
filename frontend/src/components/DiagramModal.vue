<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { Copy, Check, X, ZoomIn, ZoomOut, RotateCcw, Eye } from '@lucide/vue'
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
    fontFamily: 'monospace, sans-serif'
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
    diagramSvg.value = svg
  } catch (err: unknown) {
    console.error('Error rendering Mermaid diagram:', err)
    renderError.value = err instanceof Error ? err.message : 'Error de sintaxis en el diagrama'
  }
}

watch(
  () => [props.isOpen, props.code],
  ([newOpen]) => {
    if (newOpen) {
      zoomLevel.value = 1
      renderDiagram()
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
      class="fixed inset-0 z-[99999] bg-black/85 backdrop-blur-md flex flex-col items-center justify-center p-4 md:p-8 animate-fade-in border-0 m-0 w-full h-full max-w-none max-h-none text-inherit"
      @click.self="emit('close')"
      @cancel.prevent="emit('close')"
      @keydown="handleKeyDown"
      aria-labelledby="diagram-modal-title"
      aria-modal="true"
    >
      <!-- Modal Window -->
      <div
        class="w-full max-w-6xl h-[88vh] bg-[#060a11] border border-cyan-500/40 rounded-2xl shadow-[0_0_50px_rgba(0,229,255,0.2)] flex flex-col overflow-hidden m-auto"
      >
        <!-- Modal Header -->
        <div
          class="flex items-center justify-between px-6 py-4 border-b border-space-800 bg-[#080d1a]"
        >
          <div class="flex items-center gap-3">
            <div
              class="w-8 h-8 rounded-lg bg-neon-cyan/10 border border-neon-cyan/40 flex items-center justify-center text-neon-cyan shadow-[0_0_10px_rgba(0,229,255,0.2)]"
            >
              <Eye class="w-4 h-4" />
            </div>
            <div>
              <h3
                id="diagram-modal-title"
                class="text-sm font-mono font-bold text-white tracking-wider uppercase"
              >
                {{ title }}
              </h3>
              <span class="text-[10px] font-mono text-neon-cyan/70 tracking-widest uppercase">
                Vista Interactiva
              </span>
            </div>
          </div>

          <!-- Controls Toolbar -->
          <div class="flex items-center gap-2">
            <!-- Zoom Controls -->
            <div
              class="flex items-center bg-[#030509] border border-space-700 rounded-lg px-2 py-1 gap-2 font-mono text-xs text-slate-300"
            >
              <button
                type="button"
                @click="zoomOut"
                data-test="zoom-out-btn"
                class="p-1 hover:text-neon-cyan transition-colors"
                title="Reducir zoom"
              >
                <ZoomOut class="w-3.5 h-3.5" />
              </button>
              <span
                data-test="zoom-level-text"
                class="text-[11px] w-12 text-center text-neon-cyan font-bold select-none"
              >
                {{ Math.round(zoomLevel * 100) }}%
              </span>
              <button
                type="button"
                @click="zoomIn"
                data-test="zoom-in-btn"
                class="p-1 hover:text-neon-cyan transition-colors"
                title="Aumentar zoom"
              >
                <ZoomIn class="w-3.5 h-3.5" />
              </button>
              <button
                type="button"
                @click="resetZoom"
                data-test="zoom-reset-btn"
                class="p-1 hover:text-neon-cyan border-l border-space-800 pl-2 transition-colors"
                title="Restablecer tamaño"
              >
                <RotateCcw class="w-3.5 h-3.5" />
              </button>
            </div>

            <!-- Copy Button -->
            <button
              type="button"
              @click="copyCode"
              data-test="diagram-modal-copy-btn"
              class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-mono transition-all cursor-pointer"
              :class="
                isCopied
                  ? 'bg-emerald-500/20 border-emerald-500/60 text-emerald-300'
                  : 'bg-[#030509] border-cyan-500/40 hover:border-neon-cyan text-cyan-200 hover:text-white'
              "
              title="Copiar al portapapeles"
            >
              <Check v-if="isCopied" class="w-3.5 h-3.5 text-emerald-400" />
              <Copy v-else class="w-3.5 h-3.5" />
              <span>{{ isCopied ? 'Copiado' : 'Copiar' }}</span>
            </button>

            <!-- Close Button -->
            <button
              type="button"
              @click="emit('close')"
              data-test="diagram-modal-close-btn"
              class="p-1.5 rounded-lg bg-[#030509] border border-space-700 hover:border-red-500/50 hover:bg-red-950/30 text-slate-400 hover:text-red-400 transition-colors ml-1 cursor-pointer"
              title="Cerrar (Esc)"
            >
              <X class="w-4 h-4" />
            </button>
          </div>
        </div>

        <!-- Diagram Canvas Content -->
        <div
          ref="diagramContainerRef"
          class="flex-1 overflow-auto p-6 flex items-center justify-center bg-[#020408] relative custom-scrollbar select-none"
        >
          <!-- Error State -->
          <div
            v-if="renderError"
            class="max-w-xl p-6 bg-red-950/20 border border-red-500/40 rounded-xl text-center font-mono"
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
            class="transition-transform duration-200 ease-out origin-center flex items-center justify-center w-full h-full"
            :style="{ transform: `scale(${zoomLevel})` }"
            v-html="diagramSvg"
          ></div>

          <!-- Loading State -->
          <div v-else class="flex flex-col items-center gap-3 text-neon-cyan font-mono text-xs">
            <div class="w-6 h-6 border-2 border-neon-cyan border-t-transparent rounded-full animate-spin"></div>
            <span>Generando representación visual...</span>
          </div>
        </div>
      </div>
    </dialog>
  </Teleport>
</template>

<style scoped>
:deep(svg.mermaid-svg),
:deep(svg) {
  max-width: 100%;
  height: auto;
}
</style>
