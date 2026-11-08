<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Copy, Check, X, Download, ImageIcon, ZoomIn, ZoomOut, RotateCcw } from '@lucide/vue'

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

const copyImageUrl = async () => {
  if (!props.imageUrl) return
  try {
    await navigator.clipboard.writeText(props.imageUrl)
    isCopied.value = true
    setTimeout(() => {
      isCopied.value = false
    }, 2000)
  } catch (err) {
    console.error('Failed to copy image URL to clipboard:', err)
  }
}

const downloadImage = () => {
  if (!props.imageUrl) return
  try {
    const safeTitle = (props.title || props.alt || 'recurso_visual')
      .toLowerCase()
      .replace(/[^a-z0-9_-]+/g, '_')
      .slice(0, 30)
    const link = document.createElement('a')
    link.href = props.imageUrl
    link.download = `${safeTitle}_${Date.now()}.png`
    document.body.appendChild(link)
    link.click()
    link.remove()
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
      data-test="image-modal-backdrop"
      class="fixed inset-0 z-[99999] bg-black/85 backdrop-blur-md flex flex-col items-center justify-center p-4 md:p-8 animate-fade-in border-0 m-0 w-full h-full max-w-none max-h-none text-inherit"
      @click.self="emit('close')"
      @cancel.prevent="emit('close')"
      @keydown="handleKeyDown"
      aria-labelledby="image-modal-title"
      aria-modal="true"
    >
      <!-- Modal Window -->
      <div
        class="w-full max-w-5xl h-[88vh] bg-[#060a11] border border-cyan-500/40 rounded-2xl shadow-[0_0_50px_rgba(0,229,255,0.2)] flex flex-col overflow-hidden m-auto"
      >
        <!-- Modal Header -->
        <div
          class="flex items-center justify-between px-6 py-4 border-b border-space-800 bg-[#080d1a]"
        >
          <div class="flex items-center gap-3">
            <div
              class="w-8 h-8 rounded-lg bg-pink-500/10 border border-pink-500/40 flex items-center justify-center text-pink-400 shadow-[0_0_10px_rgba(236,72,153,0.2)]"
            >
              <ImageIcon class="w-4 h-4" />
            </div>
            <div>
              <h3
                id="image-modal-title"
                class="text-sm font-mono font-bold text-white tracking-wider uppercase"
              >
                {{ title }}
              </h3>
              <span class="text-[10px] font-mono text-pink-400/80 tracking-widest uppercase">
                Recurso Visual & Mockup UI
              </span>
            </div>
          </div>

          <!-- Controls Toolbar -->
          <div class="flex items-center gap-2">
            <!-- Zoom Controls -->
            <div class="flex items-center bg-space-800 rounded-lg p-0.5 border border-space-700 mr-2">
              <button
                type="button"
                @click="zoomOut"
                data-test="image-zoom-out-btn"
                class="p-1.5 text-slate-400 hover:text-white rounded hover:bg-space-700 transition-colors cursor-pointer"
                title="Reducir zoom"
              >
                <ZoomOut class="w-3.5 h-3.5" />
              </button>
              <span
                data-test="image-zoom-level"
                class="px-2 text-[11px] font-mono text-slate-300 min-w-11 text-center select-none"
              >
                {{ Math.round(zoomLevel * 100) }}%
              </span>
              <button
                type="button"
                @click="zoomIn"
                data-test="image-zoom-in-btn"
                class="p-1.5 text-slate-400 hover:text-white rounded hover:bg-space-700 transition-colors cursor-pointer"
                title="Aumentar zoom"
              >
                <ZoomIn class="w-3.5 h-3.5" />
              </button>
              <button
                type="button"
                @click="resetZoom"
                data-test="image-zoom-reset-btn"
                class="p-1.5 text-slate-400 hover:text-white rounded hover:bg-space-700 transition-colors cursor-pointer border-l border-space-700 ml-0.5"
                title="Restablecer zoom"
              >
                <RotateCcw class="w-3 h-3" />
              </button>
            </div>

            <!-- Copy URL Button -->
            <button
              type="button"
              @click="copyImageUrl"
              data-test="image-modal-copy-btn"
              class="relative group p-2 rounded-lg bg-space-800 hover:bg-space-700 text-slate-300 hover:text-white border border-space-700 transition-colors cursor-pointer flex items-center justify-center"
              :title="isCopied ? 'Enlace copiado' : 'Copiar enlace de la imagen'"
              :aria-label="isCopied ? 'Enlace copiado' : 'Copiar enlace de la imagen'"
            >
              <Check v-if="isCopied" class="w-4 h-4 text-emerald-400" />
              <Copy v-else class="w-4 h-4" />
              <!-- Hover Tooltip -->
              <span
                class="pointer-events-none absolute top-full mt-2 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono text-pink-300 border border-pink-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
              >
                {{ isCopied ? 'Copiado' : 'Copiar URL' }}
              </span>
            </button>

            <!-- Download Button -->
            <button
              type="button"
              @click="downloadImage"
              data-test="image-modal-download-btn"
              class="relative group p-2 rounded-lg bg-pink-500/15 hover:bg-pink-500/25 border border-pink-500 text-pink-300 transition-colors cursor-pointer flex items-center justify-center"
              title="Descargar imagen"
              aria-label="Descargar imagen"
            >
              <Download class="w-4 h-4" />
              <!-- Hover Tooltip -->
              <span
                class="pointer-events-none absolute top-full mt-2 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono font-bold text-pink-300 border border-pink-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
              >
                Descargar
              </span>
            </button>

            <!-- Close Button -->
            <button
              type="button"
              @click="emit('close')"
              data-test="image-modal-close-btn"
              class="relative group p-2 rounded-lg bg-space-800 hover:bg-space-700 text-slate-400 hover:text-white flex items-center justify-center border border-space-700 transition-colors ml-2 cursor-pointer"
              title="Cerrar (Esc)"
              aria-label="Cerrar"
            >
              <X class="w-4 h-4" />
              <!-- Hover Tooltip -->
              <span
                class="pointer-events-none absolute top-full mt-2 right-0 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono text-slate-300 border border-space-700 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
              >
                Cerrar (Esc)
              </span>
            </button>
          </div>
        </div>

        <!-- Image Viewer Body -->
        <div class="flex-1 overflow-auto p-4 md:p-8 bg-[#03060c] flex items-center justify-center custom-scrollbar">
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
      </div>
    </dialog>
  </Teleport>
</template>

