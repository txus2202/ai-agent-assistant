<script setup lang="ts">
import { computed, ref } from 'vue'
import { BookOpen, Check, Code2, Copy, Download, FileText, Printer } from '@lucide/vue'
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
  downloadMarkdownFile(props.content, effectiveTitle.value)
}

const handleExportPdf = () => {
  exportDocumentToPdf(props.content, effectiveTitle.value)
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

      <button
        type="button"
        @click="handleDownloadMd"
        data-test="document-modal-download-md-btn"
        class="relative group p-1.5 sm:p-2 rounded-lg bg-[#030509] border border-pink-500/40 hover:border-pink-400 text-pink-200 hover:text-white transition-colors cursor-pointer flex items-center justify-center shrink-0"
        title="Descargar archivo Markdown (.md)"
        aria-label="Descargar archivo Markdown (.md)"
      >
        <Download class="w-3.5 h-3.5 sm:w-4 sm:h-4" />
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
        title="Descargar / Imprimir en PDF"
        aria-label="Descargar / Imprimir en PDF"
      >
        <Printer class="w-3.5 h-3.5 sm:w-4 sm:h-4" />
        <span
          class="pointer-events-none absolute top-full mt-2 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono font-bold text-pink-300 border border-pink-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
        >
          Exportar PDF
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
