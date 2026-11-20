<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { Check, Copy, Download, Network, RotateCcw, ZoomIn, ZoomOut } from '@lucide/vue'
import mermaid from 'mermaid'
import { useModalShortcuts } from '../../composables/useModalShortcuts'
import { useTimedReset } from '../../composables/useTimedReset'
import { downloadBlobFile, sanitizeFilename } from '../../utils/fileDownload'
import { sanitizeSvg } from '../../utils/sanitize'
import DiagramViewport from './DiagramViewport.vue'
import ToolModalShell from './ToolModalShell.vue'

const props = withDefaults(
  defineProps<{
    isOpen: boolean
    code: string
    title?: string
    teleportDisabled?: boolean
  }>(),
  {
    title: 'Diagrama de Arquitectura',
    teleportDisabled: false,
  },
)

const emit = defineEmits<{
  (e: 'close'): void
}>()

const { state: isCopied, trigger: triggerCopied } = useTimedReset(false)
const zoomLevel = ref(1)
const diagramSvg = ref('')
const renderError = ref<string | null>(null)

try {
  mermaid.initialize({
    startOnLoad: false,
    theme: 'dark',
    securityLevel: 'strict',
    fontFamily: 'monospace, sans-serif',
    flowchart: {
      useMaxWidth: false,
      htmlLabels: true,
    },
    sequence: {
      useMaxWidth: false,
    },
    gantt: {
      useMaxWidth: false,
    },
    journey: {
      useMaxWidth: false,
    },
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
    diagramSvg.value = sanitizeSvg(svg.replace(/max-width:\s*[\d.]+px;?/gi, ''))
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
  { immediate: true },
)

const copyCode = async () => {
  if (!props.code) return
  try {
    await navigator.clipboard.writeText(props.code)
    triggerCopied(true)
  } catch (err) {
    console.error('Failed to copy to clipboard:', err)
  }
}

const downloadSvg = () => {
  if (!diagramSvg.value) return
  try {
    const safeTitle = sanitizeFilename(props.title, 'diagrama')
    downloadBlobFile(
      diagramSvg.value,
      `${safeTitle}_${Date.now()}.svg`,
      'image/svg+xml;charset=utf-8',
    )
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

useModalShortcuts(() => props.isOpen, handleKeyDown)
</script>

<template>
  <ToolModalShell
    :is-open="isOpen"
    backdrop-test-id="diagram-modal-backdrop"
    close-btn-test-id="diagram-modal-close-btn"
    modal-title-id="diagram-modal-title"
    title="Diagrama"
    accent-theme="cyan"
    padding-class="p-2 sm:p-4 md:p-8 pt-[max(0.75rem,env(safe-area-inset-top))] pb-[max(0.75rem,env(safe-area-inset-bottom))]"
    :teleport-disabled="teleportDisabled"
    @close="emit('close')"
  >
    <template #icon>
      <Network class="w-3.5 h-3.5 sm:w-4 sm:h-4" />
    </template>

    <template #toolbar>
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
        <span
          class="pointer-events-none absolute top-full mt-2 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono text-cyan-200 border border-cyan-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
        >
          {{ isCopied ? 'Copiado' : 'Copiar' }}
        </span>
      </button>

      <button
        type="button"
        @click="downloadSvg"
        data-test="diagram-modal-download-btn"
        class="relative group p-1.5 sm:p-2 rounded-lg bg-neon-cyan/15 hover:bg-neon-cyan/25 border border-neon-cyan text-neon-cyan transition-colors cursor-pointer flex items-center justify-center shrink-0"
        title="Descargar diagrama en formato SVG"
        aria-label="Descargar diagrama en formato SVG"
      >
        <Download class="w-3.5 h-3.5 sm:w-4 sm:h-4" />
        <span
          class="pointer-events-none absolute top-full mt-2 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono font-bold text-neon-cyan border border-neon-cyan/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
        >
          Descargar SVG
        </span>
      </button>
    </template>

    <DiagramViewport
      :render-error="renderError"
      :diagram-svg="diagramSvg"
      :code="code"
      :zoom-level="zoomLevel"
    />
  </ToolModalShell>
</template>
