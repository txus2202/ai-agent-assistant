<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Copy, Check, X, Download, Code2 } from '@lucide/vue'
import { getLanguageExtension } from '../../utils/messageParser'

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

const isCopied = ref(false)

const codeLines = computed(() => {
  return props.code ? props.code.split('\n') : []
})

const effectiveExtension = computed(() => {
  return props.extension || getLanguageExtension(props.language)
})

const copyCode = async () => {
  if (!props.code) return
  try {
    await navigator.clipboard.writeText(props.code)
    isCopied.value = true
    setTimeout(() => {
      isCopied.value = false
    }, 2000)
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
    const blob = new Blob([props.code], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
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
      data-test="code-modal-backdrop"
      class="fixed inset-0 z-[99999] bg-black/85 backdrop-blur-md flex flex-col items-center justify-center p-4 md:p-8 animate-fade-in border-0 m-0 w-full h-full max-w-none max-h-none text-inherit"
      @click.self="emit('close')"
      @cancel.prevent="emit('close')"
      @keydown="handleKeyDown"
      aria-labelledby="code-modal-title"
      aria-modal="true"
    >
      <!-- Modal Window -->
      <div
        class="w-full max-w-6xl h-[88vh] bg-[#060a11] border border-cyan-500/40 rounded-2xl shadow-[0_0_50px_rgba(0,229,255,0.2)] flex flex-col overflow-hidden m-auto"
      >
        <!-- Modal Header -->
        <div
          class="flex items-center justify-between px-6 py-4 border-b border-space-800 bg-[#080d1a]"
        >
          <div class="flex items-center gap-3">
            <div
              class="w-8 h-8 rounded-lg bg-neon-cyan/10 border border-neon-cyan/40 flex items-center justify-center text-neon-cyan shadow-[0_0_10px_rgba(0,229,255,0.2)]"
            >
              <Code2 class="w-4 h-4" />
            </div>
            <div>
              <h3
                id="code-modal-title"
                class="text-sm font-mono font-bold text-white tracking-wider uppercase flex items-center gap-2"
              >
                <span>{{ title }}</span>
                <span
                  data-test="code-modal-badge"
                  class="px-2 py-0.5 rounded bg-cyan-950/80 border border-cyan-500/30 text-[10px] text-neon-cyan font-bold"
                >
                  .{{ effectiveExtension }}
                </span>
              </h3>
              <span class="text-[10px] font-mono text-neon-cyan/70 tracking-widest uppercase">
                Artefacto de Desarrollo & Layout
              </span>
            </div>
          </div>

          <!-- Controls Toolbar -->
          <div class="flex items-center gap-2">
            <!-- Copy Button -->
            <button
              type="button"
              @click="copyCode"
              data-test="code-modal-copy-btn"
              class="relative group p-2 rounded-lg bg-space-800 hover:bg-space-700 text-slate-300 hover:text-white border border-space-700 transition-colors cursor-pointer flex items-center justify-center"
              :title="isCopied ? 'Copiado al portapapeles' : 'Copiar al portapapeles'"
              :aria-label="isCopied ? 'Copiado al portapapeles' : 'Copiar al portapapeles'"
            >
              <Check v-if="isCopied" class="w-4 h-4 text-emerald-400" />
              <Copy v-else class="w-4 h-4" />
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
              class="relative group p-2 rounded-lg bg-neon-cyan/15 hover:bg-neon-cyan/25 border border-neon-cyan text-neon-cyan transition-colors cursor-pointer flex items-center justify-center"
              :title="`Descargar .${effectiveExtension}`"
              :aria-label="`Descargar .${effectiveExtension}`"
            >
              <Download class="w-4 h-4" />
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

        <!-- Code Viewer Body -->
        <div class="flex-1 overflow-auto p-4 md:p-6 bg-[#03060c] font-mono text-xs custom-scrollbar">
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

