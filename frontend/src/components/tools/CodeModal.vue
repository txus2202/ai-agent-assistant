<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Check, Code2, Copy, Download, Eye } from '@lucide/vue'
import { useModalShortcuts } from '../../composables/useModalShortcuts'
import { useTimedReset } from '../../composables/useTimedReset'
import { downloadBlobFile, sanitizeFilename } from '../../utils/fileDownload'
import { getLanguageExtension } from '../../utils/messageParser'
import { getMimeTypeForExtension, prepareSandboxedHtml } from '../../utils/mimeHelper'
import ToolModalShell from './ToolModalShell.vue'

const props = withDefaults(
  defineProps<{
    isOpen: boolean
    code: string
    language?: string
    extension?: string
    title?: string
    teleportDisabled?: boolean
  }>(),
  {
    language: 'code',
    extension: '',
    title: 'Visualizador de Código',
    teleportDisabled: false,
  },
)

const emit = defineEmits<{
  (e: 'close'): void
}>()

const { state: isCopied, trigger: triggerCopied } = useTimedReset(false)

const effectiveExtension = computed(
  () => props.extension || getLanguageExtension(props.language),
)

const isHtml = computed(() => {
  const ext = effectiveExtension.value.toLowerCase()
  const lang = (props.language || '').toLowerCase()
  return ext === 'html' || ext === 'htm' || lang === 'html' || lang === 'htm'
})

const activeTab = ref<'preview' | 'code'>('code')

watch(
  () => [props.isOpen, isHtml.value],
  ([open, html]) => {
    if (open) {
      activeTab.value = html ? 'preview' : 'code'
    }
  },
  { immediate: true },
)

const sandboxedHtml = computed(() => (isHtml.value ? prepareSandboxedHtml(props.code) : ''))

const codeLines = computed(() => (props.code ? props.code.split('\n') : []))

const copyCode = async () => {
  if (!props.code) return
  try {
    await navigator.clipboard.writeText(props.code)
    triggerCopied(true)
  } catch (err) {
    console.error('Failed to copy code to clipboard:', err)
  }
}

const downloadCode = () => {
  if (!props.code) return
  try {
    const ext = effectiveExtension.value
    const safeTitle = sanitizeFilename(props.title, 'codigo')
    downloadBlobFile(props.code, `${safeTitle}_${Date.now()}.${ext}`, getMimeTypeForExtension(ext))
  } catch (err) {
    console.error('Failed to download code file:', err)
  }
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
    backdrop-test-id="code-modal-backdrop"
    close-btn-test-id="code-modal-close-btn"
    modal-title-id="code-modal-title"
    title="Código"
    accent-theme="cyan"
    :teleport-disabled="teleportDisabled"
    @close="emit('close')"
  >
    <template #icon>
      <Code2 class="w-3.5 h-3.5 sm:w-4 sm:h-4" />
    </template>

    <template #toolbar>
      <div
        v-if="isHtml"
        data-test="code-modal-tabs"
        class="flex items-center gap-0.5 sm:gap-1 bg-[#040810] p-0.5 sm:p-1 rounded-lg border border-cyan-500/30 mr-1 sm:mr-2"
      >
        <button
          type="button"
          @click="activeTab = 'preview'"
          data-test="code-tab-preview"
          class="relative group px-2 sm:px-2.5 py-1 rounded text-[11px] sm:text-xs font-mono transition-colors flex items-center gap-1 sm:gap-1.5 cursor-pointer"
          :class="
            activeTab === 'preview'
              ? 'bg-cyan-500/20 text-neon-cyan border border-cyan-500/40 shadow-[0_0_10px_rgba(0,229,255,0.2)]'
              : 'text-slate-400 hover:text-white'
          "
          title="Ver maquetación interactiva en sandbox seguro"
          aria-label="Vista Previa Interactiva"
        >
          <Eye class="w-3 h-3 sm:w-3.5 sm:h-3.5" />
          <span class="hidden sm:inline">Vista Previa</span>
        </button>

        <button
          type="button"
          @click="activeTab = 'code'"
          data-test="code-tab-code"
          class="relative group px-2 sm:px-2.5 py-1 rounded text-[11px] sm:text-xs font-mono transition-colors flex items-center gap-1 sm:gap-1.5 cursor-pointer"
          :class="
            activeTab === 'code'
              ? 'bg-cyan-500/20 text-neon-cyan border border-cyan-500/40 shadow-[0_0_10px_rgba(0,229,255,0.2)]'
              : 'text-slate-400 hover:text-white'
          "
          title="Ver código fuente estructurado"
          aria-label="Código Fuente"
        >
          <Code2 class="w-3 h-3 sm:w-3.5 sm:h-3.5" />
          <span class="hidden sm:inline">Código</span>
        </button>
      </div>

      <button
        type="button"
        @click="copyCode"
        data-test="code-modal-copy-btn"
        class="relative group p-1.5 sm:p-2 rounded-lg bg-space-800 hover:bg-space-700 text-slate-300 hover:text-white border border-space-700 transition-colors cursor-pointer flex items-center justify-center shrink-0"
        :title="isCopied ? 'Copiado al portapapeles' : 'Copiar al portapapeles'"
        :aria-label="isCopied ? 'Copiado al portapapeles' : 'Copiar al portapapeles'"
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
        @click="downloadCode"
        data-test="code-modal-download-btn"
        class="relative group p-1.5 sm:p-2 rounded-lg bg-neon-cyan/15 hover:bg-neon-cyan/25 border border-neon-cyan text-neon-cyan transition-colors cursor-pointer flex items-center justify-center shrink-0"
        :title="`Descargar .${effectiveExtension}`"
        :aria-label="`Descargar .${effectiveExtension}`"
      >
        <Download class="w-3.5 h-3.5 sm:w-4 sm:h-4" />
        <span
          class="pointer-events-none absolute top-full mt-2 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono font-bold text-neon-cyan border border-neon-cyan/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
        >
          Descargar .{{ effectiveExtension }}
        </span>
      </button>
    </template>

    <div
      v-if="isHtml && activeTab === 'preview'"
      data-test="code-modal-preview-container"
      class="flex-1 bg-white p-2 md:p-3 overflow-hidden flex flex-col"
    >
      <iframe
        :srcdoc="sandboxedHtml"
        sandbox="allow-scripts"
        data-test="code-modal-preview-iframe"
        class="w-full h-full border-0 rounded-lg bg-white shadow-inner"
        title="Vista Previa de Maquetación HTML"
      ></iframe>
    </div>

    <div
      v-else
      data-test="code-modal-code-container"
      class="flex-1 overflow-auto p-4 md:p-6 bg-[#03060c] font-mono text-xs custom-scrollbar"
    >
      <div class="table w-full">
        <div
          v-for="(line, idx) in codeLines"
          :key="idx"
          class="table-row hover:bg-space-900/40 transition-colors"
        >
          <span
            class="table-cell pr-4 py-0.5 text-right text-space-600 select-none w-12 font-mono text-[11px]"
          >
            {{ idx + 1 }}
          </span>
          <span class="table-cell py-0.5 text-cyan-100 whitespace-pre break-words">
            {{ line }}
          </span>
        </div>
      </div>
    </div>
  </ToolModalShell>
</template>
