<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  BookOpen,
  Check,
  ChevronDown,
  Code2,
  Copy,
  Download,
  FileCode,
  FileText,
  Printer,
} from '@lucide/vue'
import { useModalShortcuts } from '../../composables/useModalShortcuts'
import { useTimedReset } from '../../composables/useTimedReset'
import {
  downloadMarkdownFile,
  exportDocumentToPdf,
  extractDocumentTitle,
  renderMarkdownToHtml,
} from '../../utils/markdownRenderer'
import { sanitizeHtml } from '../../utils/sanitize'
import DocumentContentPane from './DocumentContentPane.vue'
import ToolModalShell from './ToolModalShell.vue'

const props = withDefaults(
  defineProps<{
    isOpen: boolean
    content: string
    title?: string
    teleportDisabled?: boolean
  }>(),
  {
    title: '',
    teleportDisabled: false,
  },
)

const emit = defineEmits<{
  (e: 'close'): void
}>()

const activeTab = ref<'preview' | 'raw'>('preview')
const { state: isCopied, trigger: triggerCopied } = useTimedReset(false)
const isDownloadMenuOpen = ref(false)
const downloadMenuRef = ref<HTMLElement | null>(null)

watch(
  () => props.isOpen,
  (open) => {
    if (open) {
      isDownloadMenuOpen.value = false
    }
  },
)

const handleClickOutside = (e: MouseEvent) => {
  if (
    isDownloadMenuOpen.value &&
    downloadMenuRef.value &&
    !downloadMenuRef.value.contains(e.target as Node)
  ) {
    isDownloadMenuOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})

const effectiveTitle = computed(
  () => props.title || extractDocumentTitle(props.content, 'Documento Técnico'),
)

const renderedHtml = computed(() => sanitizeHtml(renderMarkdownToHtml(props.content)))

const rawLines = computed(() => (props.content ? props.content.split('\n') : []))

const copyMarkdown = async () => {
  if (!props.content) return
  try {
    await navigator.clipboard.writeText(props.content)
    triggerCopied(true)
  } catch (err) {
    console.error('Failed to copy markdown content:', err)
  }
}

const handleDownloadMd = () => {
  isDownloadMenuOpen.value = false
  downloadMarkdownFile(props.content, effectiveTitle.value)
}

const handleExportPdf = () => {
  isDownloadMenuOpen.value = false
  exportDocumentToPdf(props.content, effectiveTitle.value)
}

const handleKeyDown = (event: KeyboardEvent) => {
  if (event.key === 'Escape' && props.isOpen) {
    isDownloadMenuOpen.value = false
    emit('close')
  }
}

useModalShortcuts(() => props.isOpen, handleKeyDown)
</script>

<template>
  <ToolModalShell
    :is-open="isOpen"
    backdrop-test-id="document-modal-backdrop"
    close-btn-test-id="document-modal-close-btn"
    modal-title-id="document-modal-title"
    title="Documento"
    accent-theme="pink"
    max-width-class="max-w-5xl"
    header-bg-class="bg-[#0c0814]"
    :teleport-disabled="teleportDisabled"
    @close="emit('close')"
  >
    <template #icon>
      <FileText class="w-3.5 h-3.5 sm:w-4 sm:h-4" />
    </template>

    <template #toolbar>
      <div class="flex items-center bg-space-900 border border-space-700 rounded-lg p-0.5 mr-1 sm:mr-2">
        <button
          type="button"
          @click="activeTab = 'preview'"
          data-test="doc-tab-preview"
          class="relative group px-2 sm:px-2.5 py-1 rounded text-[11px] sm:text-xs font-mono transition-colors flex items-center gap-1 sm:gap-1.5 cursor-pointer"
          :class="
            activeTab === 'preview'
              ? 'bg-pink-500/20 text-pink-300 border border-pink-500/40'
              : 'text-slate-400 hover:text-white'
          "
          title="Vista Documento Renderizado"
          aria-label="Vista Documento Renderizado"
        >
          <BookOpen class="w-3 h-3 sm:w-3.5 sm:h-3.5" />
          <span
            class="pointer-events-none absolute top-full mt-2 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono text-pink-300 border border-pink-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
          >
            Vista Previa
          </span>
        </button>

        <button
          type="button"
          @click="activeTab = 'raw'"
          data-test="doc-tab-raw"
          class="relative group px-2 sm:px-2.5 py-1 rounded text-[11px] sm:text-xs font-mono transition-colors flex items-center gap-1 sm:gap-1.5 cursor-pointer"
          :class="
            activeTab === 'raw'
              ? 'bg-pink-500/20 text-pink-300 border border-pink-500/40'
              : 'text-slate-400 hover:text-white'
          "
          title="Ver Markdown Fuente"
          aria-label="Ver Markdown Fuente"
        >
          <Code2 class="w-3.5 h-3.5" />
          <span
            class="pointer-events-none absolute top-full mt-2 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono text-pink-300 border border-pink-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
          >
            Markdown Raw
          </span>
        </button>
      </div>

      <button
        type="button"
        @click="copyMarkdown"
        data-test="document-modal-copy-btn"
        class="relative group p-1.5 sm:p-2 rounded-lg bg-[#030509] hover:bg-space-700 text-slate-300 hover:text-white border border-space-700 transition-colors cursor-pointer flex items-center justify-center shrink-0"
        :title="isCopied ? 'Markdown copiado' : 'Copiar Markdown al portapapeles'"
        :aria-label="isCopied ? 'Markdown copiado' : 'Copiar Markdown al portapapeles'"
      >
        <Check v-if="isCopied" class="w-3.5 h-3.5 sm:w-4 sm:h-4 text-emerald-400" />
        <Copy v-else class="w-3.5 h-3.5 sm:w-4 sm:h-4" />
        <span
          class="pointer-events-none absolute top-full mt-2 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono text-pink-300 border border-pink-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
        >
          {{ isCopied ? 'Copiado' : 'Copiar' }}
        </span>
      </button>

      <div class="relative" ref="downloadMenuRef">
        <button
          type="button"
          @click="isDownloadMenuOpen = !isDownloadMenuOpen"
          data-test="document-modal-download-menu-btn"
          class="relative group p-1.5 sm:p-2 rounded-lg bg-pink-500/15 hover:bg-pink-500/25 border border-pink-500 text-pink-300 transition-colors cursor-pointer flex items-center gap-1 shrink-0"
          :title="isDownloadMenuOpen ? 'Cerrar opciones de descarga' : 'Descargar documento (.pdf / .md)'"
          aria-label="Descargar documento (.pdf / .md)"
          :aria-expanded="isDownloadMenuOpen"
        >
          <Download class="w-3.5 h-3.5 sm:w-4 sm:h-4" />
          <ChevronDown
            class="w-3 h-3 transition-transform duration-200"
            :class="isDownloadMenuOpen ? 'rotate-180' : ''"
          />
          <span
            v-if="!isDownloadMenuOpen"
            class="pointer-events-none absolute top-full mt-2 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono font-bold text-pink-300 border border-pink-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
          >
            Descargar
          </span>
        </button>

        <div
          v-if="isDownloadMenuOpen"
          data-test="document-download-dropdown"
          class="absolute right-0 top-full mt-2 w-56 sm:w-64 bg-[#0c0814]/95 border border-pink-500/40 rounded-xl p-1.5 shadow-[0_0_30px_rgba(236,72,153,0.25)] backdrop-blur-md z-50 flex flex-col gap-1 font-mono text-left"
        >
          <div
            class="px-2.5 py-1 text-[10px] uppercase font-bold text-pink-400 tracking-wider border-b border-pink-500/20 mb-1"
          >
            Formato de Descarga
          </div>

          <button
            type="button"
            @click="handleExportPdf"
            data-test="document-download-option-pdf"
            class="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-slate-200 hover:text-white hover:bg-pink-950/60 border border-transparent hover:border-pink-500/30 transition-all cursor-pointer group text-left"
          >
            <div
              class="w-7 h-7 rounded bg-pink-950/80 border border-pink-500/40 flex items-center justify-center text-pink-300 group-hover:border-pink-400 shrink-0"
            >
              <Printer class="w-3.5 h-3.5" />
            </div>
            <div class="min-w-0 flex-1">
              <div class="text-xs font-bold text-pink-200 group-hover:text-white truncate">
                Documento PDF (.pdf)
              </div>
              <div class="text-[10px] text-slate-400 truncate">Exportar reporte A4 listo para imprimir</div>
            </div>
          </button>

          <button
            type="button"
            @click="handleDownloadMd"
            data-test="document-download-option-md"
            class="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-slate-200 hover:text-white hover:bg-pink-950/60 border border-transparent hover:border-pink-500/30 transition-all cursor-pointer group text-left"
          >
            <div
              class="w-7 h-7 rounded bg-pink-950/80 border border-pink-500/40 flex items-center justify-center text-pink-300 group-hover:border-pink-400 shrink-0"
            >
              <FileCode class="w-3.5 h-3.5" />
            </div>
            <div class="min-w-0 flex-1">
              <div class="text-xs font-bold text-pink-200 group-hover:text-white truncate">
                Markdown (.md)
              </div>
              <div class="text-[10px] text-slate-400 truncate">Archivo fuente estructurado</div>
            </div>
          </button>
        </div>
      </div>

      <button
        type="button"
        @click="handleDownloadMd"
        data-test="document-modal-download-md-btn"
        class="relative group p-1.5 sm:p-2 rounded-lg bg-[#030509] border border-pink-500/40 hover:border-pink-400 text-pink-200 hover:text-white transition-colors cursor-pointer flex items-center justify-center shrink-0"
        title="Descargar archivo Markdown (.md)"
        aria-label="Descargar archivo Markdown (.md)"
      >
        <FileCode class="w-3.5 h-3.5 sm:w-4 sm:h-4" />
        <span
          class="pointer-events-none absolute top-full mt-2 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono font-bold text-pink-300 border border-pink-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
        >
          Descargar .md
        </span>
      </button>

      <button
        type="button"
        @click="handleExportPdf"
        data-test="document-modal-export-pdf-btn"
        class="relative group p-1.5 sm:p-2 rounded-lg bg-pink-500/15 hover:bg-pink-500/25 border border-pink-500 text-pink-300 transition-colors cursor-pointer flex items-center justify-center shrink-0"
        title="Descargar / Imprimir en PDF (.pdf)"
        aria-label="Descargar / Imprimir en PDF (.pdf)"
      >
        <Printer class="w-3.5 h-3.5 sm:w-4 sm:h-4" />
        <span
          class="pointer-events-none absolute top-full mt-2 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono font-bold text-pink-300 border border-pink-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
        >
          Descargar .pdf
        </span>
      </button>
    </template>

    <DocumentContentPane
      :active-tab="activeTab"
      :rendered-html="renderedHtml"
      :raw-lines="rawLines"
    />
  </ToolModalShell>
</template>
