<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { MonitorPlay } from '@lucide/vue'
import { useModalShortcuts } from '../../composables/useModalShortcuts'
import { useTimedReset } from '../../composables/useTimedReset'
import {
  downloadPresentationHtml,
  downloadPresentationMarkdown,
  exportPresentationPptx,
} from '../../utils/presentationExporter'
import { parsePresentation, type PresentationData, type Slide } from '../../utils/slideParser'
import PresentationSlideStage from './PresentationSlideStage.vue'
import PresentationToolbar from './PresentationToolbar.vue'
import ToolModalShell from './ToolModalShell.vue'

const props = withDefaults(
  defineProps<{
    isOpen: boolean
    content: string
    title?: string
    teleportDisabled?: boolean
  }>(),
  {
    title: 'Presentación',
    teleportDisabled: false,
  },
)

const emit = defineEmits<{
  (e: 'close'): void
}>()

const currentSlideIndex = ref(1)
const { state: isCopied, trigger: triggerCopied, clear: clearCopied } = useTimedReset(false)
const isFullscreen = ref(false)
const isExportingPptx = ref(false)
const isDownloadMenuOpen = ref(false)
const slideDirection = ref<'forward' | 'backward'>('forward')
const shellRef = ref<InstanceType<typeof ToolModalShell> | null>(null)

const presentationData = computed<PresentationData>(() => parsePresentation(props.content))

const totalSlides = computed(() => presentationData.value.slides.length || 1)

const currentSlide = computed<Slide | undefined>(() => {
  const slides = presentationData.value.slides
  if (!slides.length) return undefined
  return slides[currentSlideIndex.value - 1] || slides[0]
})

watch(
  () => props.isOpen,
  (open) => {
    if (open) {
      currentSlideIndex.value = 1
      clearCopied()
      isCopied.value = false
      isDownloadMenuOpen.value = false
    }
  },
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

const copyContent = async () => {
  try {
    await navigator.clipboard.writeText(props.content)
    triggerCopied(true)
  } catch (err) {
    console.error('Failed to copy presentation markdown:', err)
  }
}

const selectDownloadPptx = async () => {
  isDownloadMenuOpen.value = false
  if (isExportingPptx.value) return
  isExportingPptx.value = true
  try {
    await exportPresentationPptx(
      presentationData.value,
      props.title || presentationData.value.title,
    )
  } catch (err) {
    console.error('Failed to export presentation PPTX:', err)
  } finally {
    isExportingPptx.value = false
  }
}

const selectDownloadHtml = () => {
  isDownloadMenuOpen.value = false
  downloadPresentationHtml(presentationData.value, props.title || presentationData.value.title)
}

const selectDownloadMarkdown = () => {
  isDownloadMenuOpen.value = false
  downloadPresentationMarkdown(props.content, props.title || presentationData.value.title)
}

const toggleFullscreen = () => {
  const modalEl = shellRef.value?.windowElement
  if (!modalEl) return
  if (!document.fullscreenElement) {
    modalEl
      .requestFullscreen()
      .then(() => {
        isFullscreen.value = true
      })
      .catch(() => {})
  } else {
    document
      .exitFullscreen()
      .then(() => {
        isFullscreen.value = false
      })
      .catch(() => {})
  }
}

const handleKeyDown = (e: KeyboardEvent) => {
  if (!props.isOpen || e.defaultPrevented) return

  if (e.key === 'ArrowRight' || e.key === ' ' || e.key === 'PageDown') {
    e.preventDefault()
    nextSlide()
  } else if (e.key === 'ArrowLeft' || e.key === 'PageUp') {
    e.preventDefault()
    prevSlide()
  } else if (e.key === 'Escape') {
    if (isDownloadMenuOpen.value) {
      isDownloadMenuOpen.value = false
      return
    }
    if (document.fullscreenElement) {
      document.exitFullscreen().catch(() => {})
      isFullscreen.value = false
    } else {
      emit('close')
    }
  } else if (e.key.toLowerCase() === 'f') {
    e.preventDefault()
    toggleFullscreen()
  }
}

useModalShortcuts(() => props.isOpen, handleKeyDown)
</script>

<template>
  <ToolModalShell
    ref="shellRef"
    :is-open="isOpen"
    backdrop-test-id="presentation-modal-backdrop"
    close-btn-test-id="presentation-modal-close-btn"
    modal-title-id="presentation-modal-title"
    title="Presentación"
    accent-theme="cyan"
    padding-class="p-3 sm:p-6 md:p-8 pt-[max(0.75rem,env(safe-area-inset-top))] pb-[max(0.75rem,env(safe-area-inset-bottom))]"
    select-none-window
    :teleport-disabled="teleportDisabled"
    @close="emit('close')"
  >
    <template #icon>
      <MonitorPlay class="w-3.5 h-3.5 sm:w-4 sm:h-4" />
    </template>

    <template #toolbar>
      <PresentationToolbar
        :is-fullscreen="isFullscreen"
        :is-copied="isCopied"
        :is-exporting-pptx="isExportingPptx"
        :is-download-menu-open="isDownloadMenuOpen"
        @toggle-fullscreen="toggleFullscreen"
        @copy="copyContent"
        @toggle-download-menu="isDownloadMenuOpen = !isDownloadMenuOpen"
        @close-download-menu="isDownloadMenuOpen = false"
        @download-pptx="selectDownloadPptx"
        @download-html="selectDownloadHtml"
        @download-markdown="selectDownloadMarkdown"
      />
    </template>

    <PresentationSlideStage
      :current-slide="currentSlide"
      :current-slide-index="currentSlideIndex"
      :total-slides="totalSlides"
      :slide-direction="slideDirection"
      @prev="prevSlide"
      @next="nextSlide"
      @go-to="goToSlide"
    />
  </ToolModalShell>
</template>
