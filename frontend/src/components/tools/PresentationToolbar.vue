<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import {
  Check,
  ChevronDown,
  Copy,
  Download,
  FileCode,
  Globe,
  Maximize2,
  Minimize2,
  MonitorPlay,
} from '@lucide/vue'

const props = defineProps<{
  isFullscreen: boolean
  isCopied: boolean
  isExportingPptx: boolean
  isDownloadMenuOpen: boolean
}>()

const emit = defineEmits<{
  (e: 'toggle-fullscreen'): void
  (e: 'copy'): void
  (e: 'toggle-download-menu'): void
  (e: 'close-download-menu'): void
  (e: 'download-pptx'): void
  (e: 'download-html'): void
  (e: 'download-markdown'): void
}>()

const downloadMenuRef = ref<HTMLElement | null>(null)

const handleClickOutside = (e: MouseEvent) => {
  if (
    props.isDownloadMenuOpen &&
    downloadMenuRef.value &&
    !downloadMenuRef.value.contains(e.target as Node)
  ) {
    emit('close-download-menu')
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<template>
  <button
    type="button"
    @click="emit('toggle-fullscreen')"
    data-test="presentation-modal-fullscreen-btn"
    class="relative group p-1.5 sm:p-2 rounded-lg bg-space-800 hover:bg-space-700 text-slate-300 hover:text-white border border-space-700 transition-colors cursor-pointer flex items-center justify-center shrink-0"
    :title="isFullscreen ? 'Salir de pantalla completa (Esc)' : 'Pantalla completa (F)'"
    :aria-label="isFullscreen ? 'Salir de pantalla completa' : 'Pantalla completa'"
  >
    <Minimize2 v-if="isFullscreen" class="w-3.5 h-3.5 sm:w-4 sm:h-4 text-neon-cyan" />
    <Maximize2 v-else class="w-3.5 h-3.5 sm:w-4 sm:h-4" />
    <span
      class="pointer-events-none absolute top-full mt-2 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono text-cyan-200 border border-cyan-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
    >
      {{ isFullscreen ? 'Salir' : 'Pantalla Completa' }}
    </span>
  </button>

  <button
    type="button"
    @click="emit('copy')"
    data-test="presentation-modal-copy-btn"
    class="relative group p-1.5 sm:p-2 rounded-lg bg-space-800 hover:bg-space-700 text-slate-300 hover:text-white border border-space-700 transition-colors cursor-pointer flex items-center justify-center shrink-0"
    :title="isCopied ? 'Copiado al portapapeles' : 'Copiar Markdown de diapositivas'"
    :aria-label="isCopied ? 'Copiado al portapapeles' : 'Copiar Markdown de diapositivas'"
  >
    <Check v-if="isCopied" class="w-3.5 h-3.5 sm:w-4 sm:h-4 text-emerald-400" />
    <Copy v-else class="w-3.5 h-3.5 sm:w-4 sm:h-4" />
    <span
      class="pointer-events-none absolute top-full mt-2 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono text-cyan-200 border border-cyan-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
    >
      {{ isCopied ? 'Copiado' : 'Copiar' }}
    </span>
  </button>

  <div class="relative" ref="downloadMenuRef">
    <button
      type="button"
      @click="emit('toggle-download-menu')"
      data-test="presentation-modal-download-btn"
      class="relative group p-1.5 sm:p-2 rounded-lg bg-neon-cyan/15 hover:bg-neon-cyan/25 border border-neon-cyan text-neon-cyan transition-colors cursor-pointer flex items-center gap-1 shrink-0"
      :title="isDownloadMenuOpen ? 'Cerrar opciones de descarga' : 'Descargar presentación'"
      aria-label="Descargar presentación"
      :aria-expanded="isDownloadMenuOpen"
    >
      <Download class="w-3.5 h-3.5 sm:w-4 sm:h-4" />
      <ChevronDown
        class="w-3 h-3 transition-transform duration-200"
        :class="isDownloadMenuOpen ? 'rotate-180' : ''"
      />
      <span
        v-if="!isDownloadMenuOpen"
        class="pointer-events-none absolute top-full mt-2 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono font-bold text-neon-cyan border border-neon-cyan/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
      >
        Descargar
      </span>
    </button>

    <Transition name="fade-dropdown">
      <div
        v-if="isDownloadMenuOpen"
        data-test="presentation-download-dropdown"
        class="absolute right-0 top-full mt-2 w-56 sm:w-64 bg-[#050b18]/95 border border-cyan-500/40 rounded-xl p-1.5 shadow-[0_0_30px_rgba(0,229,255,0.25)] backdrop-blur-md z-50 flex flex-col gap-1 font-mono text-left"
      >
        <div
          class="px-2.5 py-1 text-[10px] uppercase font-bold text-cyan-400 tracking-wider border-b border-cyan-500/20 mb-1"
        >
          Formato de Descarga
        </div>

        <button
          type="button"
          @click="emit('download-pptx')"
          :disabled="isExportingPptx"
          data-test="download-option-pptx"
          class="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-slate-200 hover:text-white hover:bg-cyan-950/60 border border-transparent hover:border-cyan-500/30 transition-all cursor-pointer group disabled:opacity-50 text-left"
        >
          <div
            class="w-7 h-7 rounded bg-cyan-950/80 border border-cyan-500/40 flex items-center justify-center text-cyan-300 group-hover:border-cyan-400 shrink-0"
          >
            <MonitorPlay class="w-3.5 h-3.5" />
          </div>
          <div class="min-w-0 flex-1">
            <div class="text-xs font-bold text-cyan-200 group-hover:text-white truncate">
              PowerPoint (.pptx)
            </div>
            <div class="text-[10px] text-slate-400 truncate">Diapositivas 16:9 de Atenea</div>
          </div>
        </button>

        <button
          type="button"
          @click="emit('download-html')"
          data-test="download-option-html"
          class="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-slate-200 hover:text-white hover:bg-cyan-950/60 border border-transparent hover:border-cyan-500/30 transition-all cursor-pointer group text-left"
        >
          <div
            class="w-7 h-7 rounded bg-cyan-950/80 border border-cyan-500/40 flex items-center justify-center text-cyan-300 group-hover:border-cyan-400 shrink-0"
          >
            <Globe class="w-3.5 h-3.5" />
          </div>
          <div class="min-w-0 flex-1">
            <div class="text-xs font-bold text-cyan-200 group-hover:text-white truncate">
              Web Autónoma (.html)
            </div>
            <div class="text-[10px] text-slate-400 truncate">Visor interactivo offline</div>
          </div>
        </button>

        <button
          type="button"
          @click="emit('download-markdown')"
          data-test="download-option-md"
          class="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-slate-200 hover:text-white hover:bg-cyan-950/60 border border-transparent hover:border-cyan-500/30 transition-all cursor-pointer group text-left"
        >
          <div
            class="w-7 h-7 rounded bg-cyan-950/80 border border-cyan-500/40 flex items-center justify-center text-cyan-300 group-hover:border-cyan-400 shrink-0"
          >
            <FileCode class="w-3.5 h-3.5" />
          </div>
          <div class="min-w-0 flex-1">
            <div class="text-xs font-bold text-cyan-200 group-hover:text-white truncate">
              Markdown (.md)
            </div>
            <div class="text-[10px] text-slate-400 truncate">Código de diapositivas</div>
          </div>
        </button>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.fade-dropdown-enter-active,
.fade-dropdown-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.fade-dropdown-enter-from,
.fade-dropdown-leave-to {
  opacity: 0;
  transform: translateY(-6px) scale(0.97);
}
</style>

