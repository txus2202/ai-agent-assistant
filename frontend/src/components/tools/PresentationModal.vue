<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import {
  MonitorPlay,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  Maximize2,
  Minimize2,
  Copy,
  Check,
  Download,
  X,
  Globe,
  FileCode
} from '@lucide/vue'
import { parsePresentation, type PresentationData, type Slide } from '../../utils/slideParser'
import {
  downloadPresentationHtml,
  downloadPresentationMarkdown,
  exportPresentationPptx
} from '../../utils/presentationExporter'
import { useTouchSwipe } from '../../utils/touchSwipe'

const props = withDefaults(
  defineProps<{
    isOpen: boolean
    content: string
    title?: string
    teleportDisabled?: boolean
  }>(),
  {
    title: 'Presentación',
    teleportDisabled: false
  }
)

const isTestEnv = import.meta !== undefined && import.meta.env?.MODE === 'test'
const shouldDisableTeleport = computed(() => props.teleportDisabled || isTestEnv)

const emit = defineEmits<{
  (e: 'close'): void
}>()

const currentSlideIndex = ref(1)
const isCopied = ref(false)
const isFullscreen = ref(false)
const isExportingPptx = ref(false)
const isDownloadMenuOpen = ref(false)
const slideDirection = ref<'forward' | 'backward'>('forward')
const modalRef = ref<HTMLElement | null>(null)
const stageRef = ref<HTMLElement | null>(null)
const downloadMenuRef = ref<HTMLElement | null>(null)

const presentationData = computed<PresentationData>(() => {
  return parsePresentation(props.content)
})

const totalSlides = computed(() => {
  return presentationData.value.slides.length || 1
})

const currentSlide = computed<Slide | undefined>(() => {
  const slides = presentationData.value.slides
  if (!slides.length) return undefined
  return slides[currentSlideIndex.value - 1] || slides[0]
})

// Reset slide index and dropdown when modal opens
watch(
  () => props.isOpen,
  (open) => {
    if (open) {
      currentSlideIndex.value = 1
      isCopied.value = false
      isDownloadMenuOpen.value = false
    }
  }
)

const nextSlide = () => {
  if (currentSlideIndex.value < totalSlides.value) {
    slideDirection.value = 'forward'
    currentSlideIndex.value++
  }
}

const prevSlide = () => {
  if (currentSlideIndex.value > 1) {
    slideDirection.value = 'backward'
    currentSlideIndex.value--
  }
}

const goToSlide = (idx: number) => {
  if (idx >= 1 && idx <= totalSlides.value) {
    slideDirection.value = idx >= currentSlideIndex.value ? 'forward' : 'backward'
    currentSlideIndex.value = idx
  }
}

// Touch swipe gestures to slide horizontally between slides on slide stage
useTouchSwipe(stageRef, {
  onSwipeLeft: () => {
    nextSlide()
  },
  onSwipeRight: () => {
    prevSlide()
  },
  threshold: 25
})

const copyContent = async () => {
  try {
    await navigator.clipboard.writeText(props.content)
    isCopied.value = true
    setTimeout(() => {
      isCopied.value = false
    }, 2000)
  } catch (err) {
    console.error('Failed to copy presentation markdown:', err)
  }
}

const toggleDownloadMenu = () => {
  isDownloadMenuOpen.value = !isDownloadMenuOpen.value
}

const closeDownloadMenu = () => {
  isDownloadMenuOpen.value = false
}

const handleDownloadHtml = () => {
  downloadPresentationHtml(presentationData.value, props.title || presentationData.value.title)
}

const handleDownloadPptx = async () => {
  if (isExportingPptx.value) return
  isExportingPptx.value = true
  try {
    await exportPresentationPptx(presentationData.value, props.title || presentationData.value.title)
  } catch (err) {
    console.error('Failed to export presentation PPTX:', err)
  } finally {
    isExportingPptx.value = false
  }
}

const selectDownloadPptx = async () => {
  closeDownloadMenu()
  await handleDownloadPptx()
}

const selectDownloadHtml = () => {
  closeDownloadMenu()
  handleDownloadHtml()
}

const selectDownloadMarkdown = () => {
  closeDownloadMenu()
  downloadPresentationMarkdown(props.content, props.title || presentationData.value.title)
}

const handleClickOutside = (e: MouseEvent) => {
  if (isDownloadMenuOpen.value && downloadMenuRef.value && !downloadMenuRef.value.contains(e.target as Node)) {
    closeDownloadMenu()
  }
}

const toggleFullscreen = () => {
  if (!modalRef.value) return
  if (!document.fullscreenElement) {
    modalRef.value.requestFullscreen().then(() => {
      isFullscreen.value = true
    }).catch(() => {})
  } else {
    document.exitFullscreen().then(() => {
      isFullscreen.value = false
    }).catch(() => {})
  }
}

const handleKeyDown = (e: KeyboardEvent) => {
  if (!props.isOpen) return

  if (e.key === 'ArrowRight' || e.key === ' ' || e.key === 'PageDown') {
    e.preventDefault()
    nextSlide()
  } else if (e.key === 'ArrowLeft' || e.key === 'PageUp') {
    e.preventDefault()
    prevSlide()
  } else if (e.key === 'Escape') {
    if (isDownloadMenuOpen.value) {
      closeDownloadMenu()
      return
    }
    if (document.fullscreenElement) {
      document.exitFullscreen().catch(() => {})
      isFullscreen.value = false
    } else {
      emit('close')
    }
  } else if (e.key.toLowerCase() === 'f') {
    toggleFullscreen()
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeyDown)
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
  document.removeEventListener('click', handleClickOutside)
})
</script>

<template>
  <Teleport to="body" :disabled="shouldDisableTeleport">
    <dialog
      v-if="isOpen"
      open
      data-test="presentation-modal-backdrop"
      class="fixed inset-0 z-[99999] bg-black/85 backdrop-blur-md flex flex-col items-center justify-center p-3 sm:p-6 md:p-8 pt-[max(0.75rem,env(safe-area-inset-top))] pb-[max(0.75rem,env(safe-area-inset-bottom))] animate-fade-in border-0 m-0 w-full h-full max-w-none max-h-none text-inherit"
      @click.self="emit('close')"
      @cancel.prevent="emit('close')"
      @keydown="handleKeyDown"
      aria-labelledby="presentation-modal-title"
      aria-modal="true"
    >
      <!-- Modal Window -->
      <div
        ref="modalRef"
        class="w-full max-w-6xl h-[94vh] sm:h-[88vh] max-h-[100dvh] bg-[#060a11] border border-cyan-500/40 rounded-xl sm:rounded-2xl shadow-[0_0_50px_rgba(0,229,255,0.2)] flex flex-col overflow-hidden m-auto select-none"
      >
        <!-- Modal Header (Icon - Presentación - Botones) -->
        <div
          class="flex items-center justify-between px-3 sm:px-6 py-2.5 sm:py-4 border-b border-space-800 bg-[#080d1a] gap-2 min-w-0"
        >
          <!-- Left branding: Icon - Herramienta -->
          <div class="flex items-center gap-2 sm:gap-2.5 shrink-0">
            <div
              class="w-7 h-7 sm:w-8 sm:h-8 rounded-lg bg-neon-cyan/10 border border-neon-cyan/40 flex items-center justify-center text-neon-cyan shadow-[0_0_10px_rgba(0,229,255,0.2)] shrink-0"
            >
              <MonitorPlay class="w-3.5 h-3.5 sm:w-4 sm:h-4" />
            </div>
            <h3
              id="presentation-modal-title"
              class="text-xs sm:text-sm font-mono font-bold text-neon-cyan tracking-wider uppercase select-none"
            >
              Presentación
            </h3>
          </div>

          <!-- Controls Toolbar -->
          <div class="flex items-center gap-1 sm:gap-2 shrink-0">
            <!-- Fullscreen Button -->
            <button
              type="button"
              @click="toggleFullscreen"
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

            <!-- Copy Markdown Button -->
            <button
              type="button"
              @click="copyContent"
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

            <!-- Single Download Button with Options Menu -->
            <div class="relative" ref="downloadMenuRef">
              <button
                type="button"
                @click="toggleDownloadMenu"
                data-test="presentation-modal-download-btn"
                class="relative group p-1.5 sm:p-2 rounded-lg bg-neon-cyan/15 hover:bg-neon-cyan/25 border border-neon-cyan text-neon-cyan transition-colors cursor-pointer flex items-center gap-1 shrink-0"
                :title="isDownloadMenuOpen ? 'Cerrar opciones de descarga' : 'Descargar presentación'"
                aria-label="Descargar presentación"
                :aria-expanded="isDownloadMenuOpen"
              >
                <Download class="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                <ChevronDown class="w-3 h-3 transition-transform duration-200" :class="isDownloadMenuOpen ? 'rotate-180' : ''" />
                <span
                  v-if="!isDownloadMenuOpen"
                  class="pointer-events-none absolute top-full mt-2 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono font-bold text-neon-cyan border border-neon-cyan/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
                >
                  Descargar
                </span>
              </button>

              <!-- Dropdown Menu -->
              <Transition name="fade-dropdown">
                <div
                  v-if="isDownloadMenuOpen"
                  data-test="presentation-download-dropdown"
                  class="absolute right-0 top-full mt-2 w-56 sm:w-64 bg-[#050b18]/95 border border-cyan-500/40 rounded-xl p-1.5 shadow-[0_0_30px_rgba(0,229,255,0.25)] backdrop-blur-md z-50 flex flex-col gap-1 font-mono text-left"
                >
                  <div class="px-2.5 py-1 text-[10px] uppercase font-bold text-cyan-400 tracking-wider border-b border-cyan-500/20 mb-1">
                    Formato de Descarga
                  </div>

                  <!-- Option 1: PowerPoint (.pptx) -->
                  <button
                    type="button"
                    @click="selectDownloadPptx"
                    :disabled="isExportingPptx"
                    data-test="download-option-pptx"
                    class="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-slate-200 hover:text-white hover:bg-cyan-950/60 border border-transparent hover:border-cyan-500/30 transition-all cursor-pointer group disabled:opacity-50 text-left"
                  >
                    <div class="w-7 h-7 rounded bg-cyan-950/80 border border-cyan-500/40 flex items-center justify-center text-cyan-300 group-hover:border-cyan-400 shrink-0">
                      <MonitorPlay class="w-3.5 h-3.5" />
                    </div>
                    <div class="min-w-0 flex-1">
                      <div class="text-xs font-bold text-cyan-200 group-hover:text-white truncate">
                        PowerPoint (.pptx)
                      </div>
                      <div class="text-[10px] text-slate-400 truncate">
                        Diapositivas 16:9 de Atenea
                      </div>
                    </div>
                  </button>

                  <!-- Option 2: Web Autónoma (.html) -->
                  <button
                    type="button"
                    @click="selectDownloadHtml"
                    data-test="download-option-html"
                    class="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-slate-200 hover:text-white hover:bg-cyan-950/60 border border-transparent hover:border-cyan-500/30 transition-all cursor-pointer group text-left"
                  >
                    <div class="w-7 h-7 rounded bg-cyan-950/80 border border-cyan-500/40 flex items-center justify-center text-cyan-300 group-hover:border-cyan-400 shrink-0">
                      <Globe class="w-3.5 h-3.5" />
                    </div>
                    <div class="min-w-0 flex-1">
                      <div class="text-xs font-bold text-cyan-200 group-hover:text-white truncate">
                        Web Autónoma (.html)
                      </div>
                      <div class="text-[10px] text-slate-400 truncate">
                        Visor interactivo offline
                      </div>
                    </div>
                  </button>

                  <!-- Option 3: Markdown (.md) -->
                  <button
                    type="button"
                    @click="selectDownloadMarkdown"
                    data-test="download-option-md"
                    class="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-slate-200 hover:text-white hover:bg-cyan-950/60 border border-transparent hover:border-cyan-500/30 transition-all cursor-pointer group text-left"
                  >
                    <div class="w-7 h-7 rounded bg-cyan-950/80 border border-cyan-500/40 flex items-center justify-center text-cyan-300 group-hover:border-cyan-400 shrink-0">
                      <FileCode class="w-3.5 h-3.5" />
                    </div>
                    <div class="min-w-0 flex-1">
                      <div class="text-xs font-bold text-cyan-200 group-hover:text-white truncate">
                        Markdown (.md)
                      </div>
                      <div class="text-[10px] text-slate-400 truncate">
                        Código de diapositivas
                      </div>
                    </div>
                  </button>
                </div>
              </Transition>
            </div>

            <!-- Close Button -->
            <button
              type="button"
              @click="emit('close')"
              data-test="presentation-modal-close-btn"
              class="relative group p-1.5 sm:p-2 rounded-lg bg-[#030509] border border-space-700 hover:border-red-500/50 hover:bg-red-950/30 text-slate-400 hover:text-red-400 transition-colors ml-0.5 sm:ml-1 cursor-pointer flex items-center justify-center shrink-0"
              title="Cerrar (Esc)"
              aria-label="Cerrar"
            >
              <X class="w-3.5 h-3.5 sm:w-4 sm:h-4" />
              <span
                class="pointer-events-none absolute top-full mt-2 right-0 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono text-slate-300 border border-space-700 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
              >
                Cerrar (Esc)
              </span>
            </button>
          </div>
        </div>

        <!-- Slide Navigation Sub-bar (Centered pagination below header) -->
        <div class="flex items-center justify-center py-2 px-4 bg-[#050914] border-b border-space-800 shrink-0">
          <div
            class="flex items-center bg-[#030509] border border-cyan-500/30 rounded-lg px-2 sm:px-3 py-1 gap-2 font-mono text-xs text-slate-300 shadow-sm"
          >
            <button
              type="button"
              @click="prevSlide"
              :disabled="currentSlideIndex <= 1"
              data-test="slide-prev-btn"
              class="p-1 text-slate-400 hover:text-neon-cyan disabled:opacity-30 disabled:cursor-not-allowed transition-colors cursor-pointer"
              title="Diapositiva anterior (←)"
              aria-label="Diapositiva anterior"
            >
              <ChevronLeft class="w-3.5 h-3.5 sm:w-4 sm:h-4" />
            </button>

            <span
              data-test="slide-counter"
              class="text-[11px] sm:text-xs min-w-16 text-center text-neon-cyan font-bold select-none font-mono"
            >
              {{ currentSlideIndex }} / {{ totalSlides }}
            </span>

            <button
              type="button"
              @click="nextSlide"
              :disabled="currentSlideIndex >= totalSlides"
              data-test="slide-next-btn"
              class="p-1 text-slate-400 hover:text-neon-cyan disabled:opacity-30 disabled:cursor-not-allowed transition-colors cursor-pointer"
              title="Siguiente diapositiva (→ / Espacio)"
              aria-label="Siguiente diapositiva"
            >
              <ChevronRight class="w-3.5 h-3.5 sm:w-4 sm:h-4" />
            </button>
          </div>
        </div>

        <!-- Slide Stage Body (16:9 Presentation Canvas) -->
        <div
          ref="stageRef"
          class="flex-1 overflow-y-auto overflow-x-hidden p-3 sm:p-6 md:p-8 bg-[#02050b] flex flex-col items-center relative custom-scrollbar touch-pan-y"
          style="touch-action: pan-y;"
        >
          <!-- Slide Canvas Container with 16:9 aspect ratio and subtle cybernetic glow -->
          <Transition :name="slideDirection === 'forward' ? 'slide-forward' : 'slide-backward'" mode="out-in">
            <div
              v-if="currentSlide"
              :key="currentSlide.index"
              data-test="presentation-slide-canvas"
              class="w-full max-w-4xl my-auto min-h-0 sm:min-h-[420px] bg-gradient-to-b from-[#081120] to-[#040813] border border-cyan-500/35 rounded-2xl p-4 sm:p-8 md:p-10 shadow-[0_0_50px_rgba(0,229,255,0.12)] flex flex-col justify-between transition-all duration-200"
              :class="currentSlide.layout === 'hero' ? 'text-center items-center justify-center' : ''"
            >
              <!-- Top Slide Header -->
              <div class="w-full">
                <div class="flex items-center justify-between gap-3 mb-2">
                  <span class="text-[11px] sm:text-xs font-mono font-bold uppercase tracking-widest text-cyan-400">
                    Diapositiva {{ currentSlide.index }}
                  </span>
                  <span class="text-[10px] font-mono text-cyan-400/60 uppercase">
                    Atenea Council
                  </span>
                </div>

                <h2 class="text-xl sm:text-2xl md:text-3xl font-mono font-bold text-white tracking-wide uppercase text-shadow-glow">
                  {{ currentSlide.title }}
                </h2>

                <!-- Subtitle / Executive Summary Quote -->
                <div
                  v-if="currentSlide.subtitle"
                  class="p-3 sm:p-4 my-3 sm:my-4 bg-cyan-950/40 border-l-4 border-cyan-400 rounded-r-xl text-slate-200 text-sm sm:text-base italic font-sans"
                >
                  {{ currentSlide.subtitle }}
                </div>
              </div>

              <!-- Slide Content Body (Cards or Bullets) -->
              <div class="w-full my-auto py-2">
                <!-- Cards Layout (Grid of 2 or 3 components) -->
                <div
                  v-if="currentSlide.cards && currentSlide.cards.length"
                  class="grid gap-3 sm:gap-4 my-2"
                  :class="currentSlide.cards.length === 2 ? 'grid-cols-1 md:grid-cols-2' : currentSlide.cards.length >= 3 ? 'grid-cols-1 md:grid-cols-3' : 'grid-cols-1'"
                >
                  <div
                    v-for="(card, cardIdx) in currentSlide.cards"
                    :key="cardIdx"
                    class="bg-[#050b18]/90 border border-cyan-500/30 hover:border-cyan-400/80 rounded-xl p-4 sm:p-5 shadow-[0_0_20px_rgba(0,229,255,0.06)] flex flex-col justify-between transition-all"
                  >
                    <div>
                      <div class="flex items-center justify-between gap-2 mb-2 border-b border-cyan-500/20 pb-2">
                        <h4 class="text-sm sm:text-base font-mono font-bold text-cyan-200 uppercase truncate">
                          {{ card.title }}
                        </h4>
                        <span
                          v-if="card.badge"
                          class="px-2 py-0.5 rounded bg-cyan-950/80 border border-cyan-500/40 text-[10px] font-mono font-bold text-cyan-300 uppercase shrink-0"
                        >
                          {{ card.badge }}
                        </span>
                      </div>
                      <div class="text-slate-300 text-xs sm:text-sm leading-relaxed whitespace-pre-line">
                        {{ card.content }}
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Standard Bullets Layout -->
                <ul
                  v-if="currentSlide.bullets && currentSlide.bullets.length"
                  class="list-none p-0 my-3 space-y-2.5 text-left"
                  :class="currentSlide.layout === 'hero' ? 'max-w-xl mx-auto' : ''"
                >
                  <li
                    v-for="(bullet, bIdx) in currentSlide.bullets"
                    :key="bIdx"
                    class="flex items-start gap-3 text-slate-200 text-sm sm:text-base"
                  >
                    <span class="inline-block w-2 h-2 mt-2 rounded-full bg-cyan-400 shadow-[0_0_8px_rgba(0,229,255,0.8)] shrink-0"></span>
                    <span class="leading-relaxed">{{ bullet }}</span>
                  </li>
                </ul>
              </div>

              <!-- Slide Notes / Footer info if available -->
              <div
                v-if="currentSlide.notes"
                class="w-full text-left pt-2 border-t border-cyan-500/20 text-[11px] font-mono text-cyan-300/70"
              >
                <span class="font-bold text-cyan-400">Nota:</span> {{ currentSlide.notes }}
              </div>
            </div>

            <!-- Empty State fallback -->
            <div v-else :key="'empty'" class="text-center text-slate-400 font-mono text-sm">
              No se han encontrado diapositivas estructuradas.
            </div>
          </Transition>
        </div>

        <!-- Slide Thumbnails / Indicator Bar -->
        <div class="flex items-center justify-center gap-1.5 px-4 py-2.5 bg-[#050914] border-t border-space-800">
          <button
            v-for="idx in totalSlides"
            :key="idx"
            type="button"
            @click="goToSlide(idx)"
            class="h-1.5 sm:h-2 rounded-full transition-all cursor-pointer"
            :class="idx === currentSlideIndex ? 'w-6 sm:w-8 bg-neon-cyan shadow-[0_0_10px_rgba(0,229,255,0.8)]' : 'w-2 bg-slate-700 hover:bg-slate-500'"
            :title="`Ir a diapositiva ${idx}`"
            :aria-label="`Ir a diapositiva ${idx}`"
          />
        </div>
      </div>
    </dialog>
  </Teleport>
</template>

<style scoped>
.text-shadow-glow {
  text-shadow: 0 0 15px rgba(0, 229, 255, 0.4);
}

/* Dropdown Menu Transition */
.fade-dropdown-enter-active,
.fade-dropdown-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.fade-dropdown-enter-from,
.fade-dropdown-leave-to {
  opacity: 0;
  transform: translateY(-6px) scale(0.97);
}

/* Slide Transition Animations (Slide between slides) */
.slide-forward-enter-active,
.slide-forward-leave-active,
.slide-backward-enter-active,
.slide-backward-leave-active {
  transition: opacity 0.22s ease-out, transform 0.22s cubic-bezier(0.16, 1, 0.3, 1);
}

.slide-forward-enter-from {
  opacity: 0;
  transform: translateX(40px) scale(0.98);
}
.slide-forward-leave-to {
  opacity: 0;
  transform: translateX(-40px) scale(0.98);
}

.slide-backward-enter-from {
  opacity: 0;
  transform: translateX(-40px) scale(0.98);
}
.slide-backward-leave-to {
  opacity: 0;
  transform: translateX(40px) scale(0.98);
}
</style>

