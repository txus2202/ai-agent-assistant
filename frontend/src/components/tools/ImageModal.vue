<script setup lang="ts">
import { ref } from 'vue'
import { Check, Copy, Download, ImageIcon, RotateCcw, ZoomIn, ZoomOut } from '@lucide/vue'
import { useModalShortcuts } from '../../composables/useModalShortcuts'
import { useTimedReset } from '../../composables/useTimedReset'
import { downloadUrlFile, sanitizeFilename } from '../../utils/fileDownload'
import ToolModalShell from './ToolModalShell.vue'

const props = withDefaults(
  defineProps<{
    isOpen: boolean
    imageUrl: string
    alt?: string
    title?: string
    teleportDisabled?: boolean
  }>(),
  {
    alt: 'Recurso visual',
    title: 'Visualizador de Imagen',
    teleportDisabled: false,
  },
)

const emit = defineEmits<{
  (e: 'close'): void
}>()

const { state: isCopied, trigger: triggerCopied } = useTimedReset(false)
const zoomLevel = ref(1)

const copyImageUrl = async () => {
  if (!props.imageUrl) return
  try {
    await navigator.clipboard.writeText(props.imageUrl)
    triggerCopied(true)
  } catch (err) {
    console.error('Failed to copy image URL to clipboard:', err)
  }
}

const downloadImage = () => {
  if (!props.imageUrl) return
  try {
    const safeTitle = sanitizeFilename(props.title || props.alt, 'recurso_visual')
    downloadUrlFile(props.imageUrl, `${safeTitle}_${Date.now()}.png`)
  } catch (err) {
    console.error('Failed to download image:', err)
  }
}

const zoomIn = () => {
  if (zoomLevel.value < 3) {
    zoomLevel.value = Math.round((zoomLevel.value + 0.2) * 10) / 10
  }
}

const zoomOut = () => {
  if (zoomLevel.value > 0.4) {
    zoomLevel.value = Math.round((zoomLevel.value - 0.2) * 10) / 10
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
    backdrop-test-id="image-modal-backdrop"
    close-btn-test-id="image-modal-close-btn"
    modal-title-id="image-modal-title"
    title="Imágenes"
    accent-theme="pink"
    max-width-class="max-w-5xl"
    :teleport-disabled="teleportDisabled"
    @close="emit('close')"
  >
    <template #icon>
      <ImageIcon class="w-3.5 h-3.5 sm:w-4 sm:h-4" />
    </template>

    <template #toolbar>
      <div
        class="flex items-center bg-[#030509] rounded-lg px-1 sm:px-2 py-0.5 sm:py-1 border border-space-700 font-mono text-xs text-slate-300"
      >
        <button
          type="button"
          @click="zoomOut"
          data-test="image-zoom-out-btn"
          class="p-1 text-slate-400 hover:text-pink-300 transition-colors cursor-pointer"
          title="Reducir zoom"
          aria-label="Reducir zoom"
        >
          <ZoomOut class="w-3.5 h-3.5" />
        </button>
        <span
          data-test="image-zoom-level"
          class="text-[10px] sm:text-[11px] w-8 sm:w-11 text-center text-pink-300 font-bold select-none"
        >
          {{ Math.round(zoomLevel * 100) }}%
        </span>
        <button
          type="button"
          @click="zoomIn"
          data-test="image-zoom-in-btn"
          class="p-1 text-slate-400 hover:text-pink-300 transition-colors cursor-pointer"
          title="Aumentar zoom"
          aria-label="Aumentar zoom"
        >
          <ZoomIn class="w-3.5 h-3.5" />
        </button>
        <button
          type="button"
          @click="resetZoom"
          data-test="image-zoom-reset-btn"
          class="p-1 text-slate-400 hover:text-pink-300 transition-colors cursor-pointer border-l border-space-700 ml-0.5"
          title="Restablecer zoom"
          aria-label="Restablecer zoom"
        >
          <RotateCcw class="w-3 h-3" />
        </button>
      </div>

      <button
        type="button"
        @click="copyImageUrl"
        data-test="image-modal-copy-btn"
        class="relative group p-1.5 sm:p-2 rounded-lg bg-[#030509] hover:bg-space-700 text-slate-300 hover:text-white border border-space-700 transition-colors cursor-pointer flex items-center justify-center shrink-0"
        :title="isCopied ? 'Enlace copiado' : 'Copiar enlace de la imagen'"
        :aria-label="isCopied ? 'Enlace copiado' : 'Copiar enlace de la imagen'"
      >
        <Check v-if="isCopied" class="w-3.5 h-3.5 sm:w-4 sm:h-4 text-emerald-400" />
        <Copy v-else class="w-3.5 h-3.5 sm:w-4 sm:h-4" />
        <span
          class="pointer-events-none absolute top-full mt-2 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono text-pink-300 border border-pink-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
        >
          {{ isCopied ? 'Copiado' : 'Copiar URL' }}
        </span>
      </button>

      <button
        type="button"
        @click="downloadImage"
        data-test="image-modal-download-btn"
        class="relative group p-1.5 sm:p-2 rounded-lg bg-pink-500/15 hover:bg-pink-500/25 border border-pink-500 text-pink-300 transition-colors cursor-pointer flex items-center justify-center shrink-0"
        title="Descargar imagen"
        aria-label="Descargar imagen"
      >
        <Download class="w-3.5 h-3.5 sm:w-4 sm:h-4" />
        <span
          class="pointer-events-none absolute top-full mt-2 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono font-bold text-pink-300 border border-pink-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
        >
          Descargar
        </span>
      </button>
    </template>

    <div
      class="flex-1 overflow-auto p-4 md:p-8 bg-[#03060c] flex items-center justify-center custom-scrollbar"
    >
      <div
        class="transition-transform duration-150 ease-out origin-center"
        :style="{ transform: `scale(${zoomLevel})` }"
      >
        <img
          :src="imageUrl"
          :alt="alt"
          data-test="image-modal-img"
          class="max-w-full max-h-[70vh] rounded-lg border border-space-800 shadow-2xl object-contain"
        />
      </div>
    </div>
  </ToolModalShell>
</template>
