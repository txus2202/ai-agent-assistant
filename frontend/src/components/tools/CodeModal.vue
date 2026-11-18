<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useModalShortcuts } from '../../composables/useModalShortcuts'
import { useTimedReset } from '../../composables/useTimedReset'
import { Copy, Check, X, Download, Code2, Eye } from '@lucide/vue'
import { getLanguageExtension } from '../../utils/messageParser'
import { getMimeTypeForExtension, prepareSandboxedHtml } from '../../utils/mimeHelper'

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
    teleportDisabled: false
  }
)

const isTestEnv = import.meta !== undefined && import.meta.env?.MODE === 'test'
const shouldDisableTeleport = computed(() => props.teleportDisabled || isTestEnv)

const emit = defineEmits<{
  (e: 'close'): void
}>()

const { state: isCopied, trigger: triggerCopied } = useTimedReset(false)

const effectiveExtension = computed(() => {
  return props.extension || getLanguageExtension(props.language)
})

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
  { immediate: true }
)

const sandboxedHtml = computed(() => {
  return isHtml.value ? prepareSandboxedHtml(props.code) : ''
})

const codeLines = computed(() => {
  return props.code ? props.code.split('\n') : []
})

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
    const safeTitle = (props.title || 'codigo')
      .toLowerCase()
      .replace(/[^a-z0-9_-]+/g, '_')
      .slice(0, 30)
    const filename = `${safeTitle}_${Date.now()}.${ext}`
    const mimeType = getMimeTypeForExtension(ext)
    const blob = new Blob([props.code], { type: mimeType })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
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
  <Teleport to="body" :disabled="shouldDisableTeleport">
    <dialog
      v-if="isOpen"
      open
      data-test="code-modal-backdrop"
      class="fixed inset-0 z-[99999] bg-black/85 backdrop-blur-md flex flex-col items-center justify-center p-4 md:p-8 pt-[max(1rem,env(safe-area-inset-top))] pb-[max(1rem,env(safe-area-inset-bottom))] animate-fade-in border-0 m-0 w-full h-full max-w-none max-h-none text-inherit"
      @click.self="emit('close')"
      @cancel.prevent="emit('close')"
      aria-labelledby="code-modal-title"
      aria-modal="true"
    >
      <!-- Modal Window -->
      <div
        class="w-full max-w-6xl h-[94vh] sm:h-[88vh] max-h-[100dvh] bg-[#060a11] border border-cyan-500/40 rounded-xl sm:rounded-2xl shadow-[0_0_50px_rgba(0,229,255,0.2)] flex flex-col overflow-hidden m-auto"
      >
        <!-- Modal Header -->
        <div
          class="flex items-center justify-between px-3 sm:px-6 py-2.5 sm:py-4 border-b border-space-800 bg-[#080d1a] gap-2 min-w-0"
        >
          <!-- Left branding: Icon - Herramienta -->
          <div class="flex items-center gap-2 sm:gap-2.5 shrink-0">
            <div
              class="w-7 h-7 sm:w-8 sm:h-8 rounded-lg bg-neon-cyan/10 border border-neon-cyan/40 flex items-center justify-center text-neon-cyan shadow-[0_0_10px_rgba(0,229,255,0.2)] shrink-0"
            >
              <Code2 class="w-3.5 h-3.5 sm:w-4 sm:h-4" />
            </div>
            <h3
              id="code-modal-title"
              class="text-xs sm:text-sm font-mono font-bold text-neon-cyan tracking-wider uppercase select-none"
            >
              Código
            </h3>
          </div>

          <!-- Controls Toolbar -->
          <div class="flex items-center gap-1 sm:gap-2 shrink-0">
            <!-- Tab Switcher (Visible only for HTML/HTM) -->
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
                :class="activeTab === 'preview' ? 'bg-cyan-500/20 text-neon-cyan border border-cyan-500/40 shadow-[0_0_10px_rgba(0,229,255,0.2)]' : 'text-slate-400 hover:text-white'"
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
                :class="activeTab === 'code' ? 'bg-cyan-500/20 text-neon-cyan border border-cyan-500/40 shadow-[0_0_10px_rgba(0,229,255,0.2)]' : 'text-slate-400 hover:text-white'"
                title="Ver código fuente estructurado"
                aria-label="Código Fuente"
              >
                <Code2 class="w-3 h-3 sm:w-3.5 sm:h-3.5" />
                <span class="hidden sm:inline">Código</span>
              </button>
            </div>

            <!-- Copy Button -->
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
              <!-- Hover Tooltip -->
              <span
                class="pointer-events-none absolute top-full mt-2 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono text-cyan-200 border border-cyan-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
              >
                {{ isCopied ? 'Copiado' : 'Copiar' }}
              </span>
            </button>

            <!-- Download Button -->
            <button
              type="button"
              @click="downloadCode"
              data-test="code-modal-download-btn"
              class="relative group p-1.5 sm:p-2 rounded-lg bg-neon-cyan/15 hover:bg-neon-cyan/25 border border-neon-cyan text-neon-cyan transition-colors cursor-pointer flex items-center justify-center shrink-0"
              :title="`Descargar .${effectiveExtension}`"
              :aria-label="`Descargar .${effectiveExtension}`"
            >
              <Download class="w-3.5 h-3.5 sm:w-4 sm:h-4" />
              <!-- Hover Tooltip -->
              <span
                class="pointer-events-none absolute top-full mt-2 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono font-bold text-neon-cyan border border-neon-cyan/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
              >
                Descargar .{{ effectiveExtension }}
              </span>
            </button>

            <!-- Close Button -->
            <button
              type="button"
              @click="emit('close')"
              data-test="code-modal-close-btn"
              class="relative group p-1.5 sm:p-2 rounded-lg bg-[#030509] border border-space-700 hover:border-red-500/50 hover:bg-red-950/30 text-slate-400 hover:text-red-400 transition-colors ml-0.5 sm:ml-1 cursor-pointer flex items-center justify-center shrink-0"
              title="Cerrar (Esc)"
              aria-label="Cerrar"
            >
              <X class="w-3.5 h-3.5 sm:w-4 sm:h-4" />
              <!-- Hover Tooltip -->
              <span
                class="pointer-events-none absolute top-full mt-2 right-0 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono text-slate-300 border border-space-700 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
              >
                Cerrar (Esc)
              </span>
            </button>
          </div>
        </div>

        <!-- Modal Body: Interactive Sandboxed Preview (Only for HTML) -->
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

        <!-- Modal Body: Code Viewer (Numbered Lines) -->
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
      </div>
    </dialog>
  </Teleport>
</template>
