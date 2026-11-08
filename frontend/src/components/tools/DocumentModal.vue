<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import {
  FileText,
  Copy,
  Check,
  Download,
  Printer,
  X,
  Code2,
  BookOpen
} from '@lucide/vue'
import {
  renderMarkdownToHtml,
  downloadMarkdownFile,
  exportDocumentToPdf,
  extractDocumentTitle
} from '../../utils/markdownRenderer'

const props = withDefaults(
  defineProps<{
    isOpen: boolean
    content: string
    title?: string
    teleportDisabled?: boolean
  }>(),
  {
    title: '',
    teleportDisabled: false
  }
)

const isTestEnv = import.meta !== undefined && import.meta.env?.MODE === 'test'
const shouldDisableTeleport = computed(() => props.teleportDisabled || isTestEnv)

const emit = defineEmits<{
  (e: 'close'): void
}>()

const activeTab = ref<'preview' | 'raw'>('preview')
const isCopied = ref(false)

const effectiveTitle = computed(() => {
  return props.title || extractDocumentTitle(props.content, 'Documento Técnico')
})

const renderedHtml = computed(() => {
  return renderMarkdownToHtml(props.content)
})

const rawLines = computed(() => {
  return props.content ? props.content.split('\n') : []
})

const copyMarkdown = async () => {
  if (!props.content) return
  try {
    await navigator.clipboard.writeText(props.content)
    isCopied.value = true
    setTimeout(() => {
      isCopied.value = false
    }, 2000)
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
      data-test="document-modal-backdrop"
      class="fixed inset-0 z-[99999] bg-black/85 backdrop-blur-md flex flex-col items-center justify-center p-4 md:p-8 animate-fade-in border-0 m-0 w-full h-full max-w-none max-h-none text-inherit"
      @click.self="emit('close')"
      @cancel.prevent="emit('close')"
      @keydown="handleKeyDown"
      aria-labelledby="document-modal-title"
      aria-modal="true"
    >
      <!-- Modal Window -->
      <div
        class="w-full max-w-5xl h-[88vh] bg-[#060a11] border border-pink-500/40 rounded-2xl shadow-[0_0_50px_rgba(236,72,153,0.15)] flex flex-col overflow-hidden m-auto"
      >
        <!-- Modal Header -->
        <div
          class="flex items-center justify-between px-6 py-4 border-b border-space-800 bg-[#0c0814]"
        >
          <div class="flex items-center gap-3">
            <div
              class="w-8 h-8 rounded-lg bg-pink-500/10 border border-pink-500/40 flex items-center justify-center text-pink-400 shadow-[0_0_10px_rgba(236,72,153,0.2)]"
            >
              <FileText class="w-4 h-4" />
            </div>
            <div>
              <h3
                id="document-modal-title"
                class="text-sm font-mono font-bold text-white tracking-wider uppercase flex items-center gap-2"
              >
                <span>{{ effectiveTitle }}</span>
                <span
                  class="px-2 py-0.5 rounded bg-pink-950/80 border border-pink-500/30 text-[10px] text-pink-300 font-bold"
                >
                  .md / .pdf
                </span>
              </h3>
              <span class="text-[10px] font-mono text-pink-400/80 tracking-widest uppercase">
                Herramienta de Documentación Técnica (Calíope)
              </span>
            </div>
          </div>

          <!-- Controls Toolbar -->
          <div class="flex items-center gap-2">
            <!-- Mode Toggle Tabs -->
            <div class="flex items-center bg-space-900 border border-space-700 rounded-lg p-0.5 mr-2">
              <button
                type="button"
                @click="activeTab = 'preview'"
                data-test="doc-tab-preview"
                class="relative group px-2.5 py-1 rounded text-xs font-mono transition-colors flex items-center gap-1.5 cursor-pointer"
                :class="activeTab === 'preview' ? 'bg-pink-500/20 text-pink-300 border border-pink-500/40' : 'text-slate-400 hover:text-white'"
                title="Vista Documento Renderizado"
                aria-label="Vista Documento Renderizado"
              >
                <BookOpen class="w-3.5 h-3.5" />
                <!-- Hover Tooltip -->
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
                class="relative group px-2.5 py-1 rounded text-xs font-mono transition-colors flex items-center gap-1.5 cursor-pointer"
                :class="activeTab === 'raw' ? 'bg-pink-500/20 text-pink-300 border border-pink-500/40' : 'text-slate-400 hover:text-white'"
                title="Ver Markdown Fuente"
                aria-label="Ver Markdown Fuente"
              >
                <Code2 class="w-3.5 h-3.5" />
                <!-- Hover Tooltip -->
                <span
                  class="pointer-events-none absolute top-full mt-2 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono text-pink-300 border border-pink-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
                >
                  Markdown Raw
                </span>
              </button>
            </div>

            <!-- Copy Markdown Button -->
            <button
              type="button"
              @click="copyMarkdown"
              data-test="document-modal-copy-btn"
              class="relative group p-2 rounded-lg bg-space-800 hover:bg-space-700 text-slate-300 hover:text-white border border-space-700 transition-colors cursor-pointer flex items-center justify-center"
              :title="isCopied ? 'Markdown copiado' : 'Copiar Markdown al portapapeles'"
              :aria-label="isCopied ? 'Markdown copiado' : 'Copiar Markdown al portapapeles'"
            >
              <Check v-if="isCopied" class="w-4 h-4 text-emerald-400" />
              <Copy v-else class="w-4 h-4" />
              <!-- Hover Tooltip -->
              <span
                class="pointer-events-none absolute top-full mt-2 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono text-pink-300 border border-pink-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
              >
                {{ isCopied ? 'Copiado' : 'Copiar' }}
              </span>
            </button>

            <!-- Download .md Button -->
            <button
              type="button"
              @click="handleDownloadMd"
              data-test="document-modal-download-md-btn"
              class="relative group p-2 rounded-lg bg-[#030509] border border-pink-500/40 hover:border-pink-400 text-pink-200 hover:text-white transition-colors cursor-pointer flex items-center justify-center"
              title="Descargar archivo Markdown (.md)"
              aria-label="Descargar archivo Markdown (.md)"
            >
              <Download class="w-4 h-4" />
              <!-- Hover Tooltip -->
              <span
                class="pointer-events-none absolute top-full mt-2 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono font-bold text-pink-300 border border-pink-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
              >
                Descargar .md
              </span>
            </button>

            <!-- Export PDF Button -->
            <button
              type="button"
              @click="handleExportPdf"
              data-test="document-modal-export-pdf-btn"
              class="relative group p-2 rounded-lg bg-pink-500/15 hover:bg-pink-500/25 border border-pink-500 text-pink-300 transition-colors cursor-pointer flex items-center justify-center"
              title="Descargar / Imprimir en PDF"
              aria-label="Descargar / Imprimir en PDF"
            >
              <Printer class="w-4 h-4" />
              <!-- Hover Tooltip -->
              <span
                class="pointer-events-none absolute top-full mt-2 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono font-bold text-pink-300 border border-pink-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
              >
                Exportar PDF
              </span>
            </button>

            <!-- Close Button -->
            <button
              type="button"
              @click="emit('close')"
              data-test="document-modal-close-btn"
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

        <!-- Rendered Document View -->
        <div
          v-if="activeTab === 'preview'"
          data-test="document-preview-container"
          class="flex-1 overflow-auto p-6 md:p-10 bg-[#02050a] text-slate-200 leading-relaxed custom-scrollbar selection:bg-pink-500/30"
        >
          <div class="max-w-3xl mx-auto doc-body font-sans text-sm" v-html="renderedHtml"></div>
        </div>

        <!-- Raw Markdown View -->
        <div
          v-else
          data-test="document-raw-container"
          class="flex-1 overflow-auto p-4 md:p-6 bg-[#03060c] font-mono text-xs custom-scrollbar"
        >
          <div class="table w-full">
            <div
              v-for="(line, idx) in rawLines"
              :key="idx"
              class="table-row hover:bg-space-900/40 transition-colors"
            >
              <span
                class="table-cell pr-4 py-0.5 text-right text-space-600 select-none w-12 font-mono text-[11px]"
              >
                {{ idx + 1 }}
              </span>
              <span class="table-cell py-0.5 text-pink-100 whitespace-pre break-words">
                {{ line }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </dialog>
  </Teleport>
</template>

<style scoped>
:deep(.doc-h1) {
  font-size: 1.5rem;
  font-weight: 800;
  color: #ffffff;
  border-bottom: 1px solid rgba(236, 72, 153, 0.4);
  padding-bottom: 0.5rem;
  margin-top: 0;
  margin-bottom: 1.25rem;
  letter-spacing: -0.025em;
}

:deep(.doc-h2) {
  font-size: 1.25rem;
  font-weight: 700;
  color: #fce7f3;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  padding-bottom: 0.35rem;
  margin-top: 1.75rem;
  margin-bottom: 0.75rem;
}

:deep(.doc-h3) {
  font-size: 1.05rem;
  font-weight: 600;
  color: #fbcfe8;
  margin-top: 1.25rem;
  margin-bottom: 0.5rem;
}

:deep(.doc-p) {
  margin-top: 0;
  margin-bottom: 0.85rem;
  line-height: 1.7;
  color: #cbd5e1;
}

:deep(.doc-ul), :deep(.doc-ol) {
  margin-top: 0.25rem;
  margin-bottom: 1rem;
  padding-left: 1.5rem;
  color: #cbd5e1;
}

:deep(.doc-ul) {
  list-style-type: disc;
}

:deep(.doc-ol) {
  list-style-type: decimal;
}

:deep(li) {
  margin-bottom: 0.35rem;
  line-height: 1.6;
}

:deep(.doc-code-block) {
  background: #060a12;
  border: 1px solid rgba(236, 72, 153, 0.25);
  border-radius: 0.5rem;
  padding: 0.85rem 1rem;
  font-family: ui-monospace, monospace;
  font-size: 0.8rem;
  color: #fce7f3;
  overflow-x: auto;
  margin: 1rem 0;
}

:deep(.doc-inline-code) {
  background: #1e0e1a;
  border: 1px solid rgba(236, 72, 153, 0.3);
  padding: 0.15rem 0.35rem;
  border-radius: 0.25rem;
  font-family: ui-monospace, monospace;
  font-size: 0.8rem;
  color: #ffffff;
}

:deep(.doc-blockquote) {
  border-left: 3px solid #ec4899;
  padding-left: 1rem;
  margin: 1rem 0;
  color: #ffffff;
  font-style: italic;
  background: #100b14;
  padding-top: 0.25rem;
  padding-bottom: 0.25rem;
  border-radius: 0 0.25rem 0.25rem 0;
}

:deep(.doc-table) {
  width: 100%;
  border-collapse: collapse;
  margin: 1.25rem 0;
  font-size: 0.85rem;
}

:deep(.doc-table th), :deep(.doc-table td) {
  border: 1px solid rgba(255, 255, 255, 0.15);
  padding: 0.6rem 0.85rem;
  text-align: left;
}

:deep(.doc-table th) {
  background: #1a0b16;
  color: #ffffff;
  font-weight: 700;
}

:deep(.doc-hr) {
  border: 0;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  margin: 1.5rem 0;
}
</style>

