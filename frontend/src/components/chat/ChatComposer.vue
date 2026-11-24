<script setup lang="ts">
import { ref } from 'vue'
import { ArrowDown, ArrowUp, Brain, ChevronDown, Paperclip, SendHorizontal } from '@lucide/vue'
import type { VaultDomainItem } from '../../services/debateApiService'
import ChatAgentSelector from './ChatAgentSelector.vue'
import type { SelectableAgentOption } from './types'

const props = defineProps<{
  draftMessage: string
  selectedAgents: string[]
  agentsList: SelectableAgentOption[]
  availableDomains: VaultDomainItem[]
  selectedDomain: string
  selectedFilesCount: number
  isHitlRequired: boolean
  isDebating: boolean
  isChatScrollable: boolean
  scrollDirection: 'up' | 'down'
}>()

const emit = defineEmits<{
  (e: 'update:draftMessage', value: string): void
  (e: 'update:selectedAgents', value: string[]): void
  (e: 'update:selectedDomain', value: string): void
  (e: 'files-selected', event: Event): void
  (e: 'scroll-toggle'): void
  (e: 'submit'): void
}>()

const chatInputRef = ref<HTMLTextAreaElement | null>(null)

const focusInput = () => {
  chatInputRef.value?.focus()
}

const isTouchOrMobileDevice = (): boolean => {
  if (typeof window === 'undefined') return false
  const isCoarse =
    window.matchMedia('(pointer: coarse)').matches ||
    /Android|iPhone|iPad|iPod/i.test(navigator?.userAgent || '')
  const isSmallScreen = window.matchMedia('(max-width: 768px)').matches
  return isCoarse && isSmallScreen
}

const handleKeyDown = (event: KeyboardEvent) => {
  if (event.key !== 'Enter') return

  // Durante composición IME o dictado de voz, no interceptar
  if (event.isComposing) return

  // Shift + Enter: siempre salto de línea (comportamiento nativo de textarea)
  if (event.shiftKey) {
    return
  }

  // Ctrl + Enter o Cmd + Enter: forzar envío (atajo para desktop y tablets)
  if (event.ctrlKey || event.metaKey) {
    event.preventDefault()
    if (props.draftMessage.trim() && !(props.isDebating && !props.isHitlRequired)) {
      emit('submit')
    }
    return
  }

  // En teclado móvil/táctil: Enter hace salto de línea (para enviar se pulsa el botón)
  if (isTouchOrMobileDevice()) {
    return
  }

  // En escritorio con teclado físico: Enter envía el mensaje
  event.preventDefault()
  if (props.draftMessage.trim() && !(props.isDebating && !props.isHitlRequired)) {
    emit('submit')
  }
}

defineExpose({
  focusInput,
})
</script>

<template>
  <form @submit.prevent="emit('submit')" class="flex flex-col gap-2.5 md:gap-3 relative">
    <!-- Metis Learning Mode Context Bar -->
    <div
      v-if="selectedAgents.includes('learning')"
      data-test="metis-context-banner"
      class="bg-[#041220]/95 border border-neon-cyan/40 rounded-lg px-3 py-2 flex flex-wrap items-center justify-between gap-2.5 shadow-[0_0_15px_-3px_rgba(0,229,255,0.12)] animate-fade-in"
    >
      <div class="flex items-center gap-2 flex-1 min-w-[200px]">
        <Brain class="w-3.5 h-3.5 text-neon-cyan animate-pulse shrink-0" title="Metis" />

        <div class="relative flex-1 max-w-full sm:max-w-xs">
          <select
            id="vault-domain-selector"
            :value="selectedDomain"
            @change="emit('update:selectedDomain', ($event.target as HTMLSelectElement).value)"
            data-test="vault-domain-selector"
            aria-label="Seleccionar dominio del Vault"
            class="w-full bg-[#030914] text-[11px] font-mono text-cyan-200 border border-cyan-800/80 hover:border-neon-cyan rounded pl-2.5 pr-7 py-1 min-h-[30px] focus:outline-none focus:border-neon-cyan cursor-pointer transition-colors appearance-none truncate shadow-inner"
            title="Dominio del Vault donde se catalogará este conocimiento"
          >
            <option value="">🎯 Automático (según contenido)</option>
            <option v-for="domain in availableDomains" :key="domain.id" :value="domain.id">
              📁 {{ domain.name }}
            </option>
          </select>
          <ChevronDown
            class="w-3 h-3 text-cyan-400 pointer-events-none absolute right-2 top-1/2 -translate-y-1/2"
          />
        </div>
      </div>

      <div class="flex items-center shrink-0">
        <label
          for="chat-file-upload"
          class="cursor-pointer text-cyan-300 hover:text-white transition-colors flex items-center gap-1.5 px-2.5 py-1 min-h-[30px] border border-cyan-800/80 rounded bg-[#030914] hover:bg-cyan-950/80 hover:border-neon-cyan text-[11px] font-mono shadow-sm"
          title="Adjuntar PDF, Markdown o Imagen para Metis"
        >
          <Paperclip class="w-3.5 h-3.5 text-neon-cyan shrink-0" />
          <span class="text-[10px] md:text-[11px]">
            {{ selectedFilesCount > 0 ? `${selectedFilesCount} archivo(s)` : 'Adjuntar' }}
          </span>
          <input
            id="chat-file-upload"
            type="file"
            multiple
            accept=".pdf,.md,.markdown,.png,.jpg,.jpeg,.webp"
            @change="emit('files-selected', $event)"
            class="hidden"
            data-test="file-input"
          />
        </label>
      </div>
    </div>

    <div class="flex items-center justify-between gap-2">
      <div class="flex items-center gap-2">
        <ChatAgentSelector
          :agents="agentsList"
          :selected-agents="selectedAgents"
          :disabled="isDebating && !isHitlRequired"
          @update:selected-agents="emit('update:selectedAgents', $event)"
        />
      </div>

      <button
        v-if="isChatScrollable"
        type="button"
        @click="emit('scroll-toggle')"
        data-test="chat-scroll-toggle-btn"
        class="relative group flex items-center justify-center min-h-[36px] min-w-[36px] md:min-h-0 md:h-[28px] md:w-[28px] bg-[#030509] border border-cyan-900/50 hover:border-neon-cyan/80 text-cyan-300 hover:text-white rounded shadow-[0_0_10px_-2px_rgba(0,229,255,0.1)] hover:shadow-[0_0_12px_rgba(0,229,255,0.3)] transition-all cursor-pointer shrink-0"
        :title="scrollDirection === 'down' ? 'Bajar al final del chat' : 'Subir al inicio del chat'"
        :aria-label="
          scrollDirection === 'down' ? 'Bajar al final del chat' : 'Subir al inicio del chat'
        "
      >
        <ArrowDown v-if="scrollDirection === 'down'" class="w-3.5 h-3.5" />
        <ArrowUp v-else class="w-3.5 h-3.5" />
        <span
          class="pointer-events-none absolute bottom-full mb-1.5 right-0 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono text-cyan-200 border border-cyan-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
        >
          {{ scrollDirection === 'down' ? 'Bajar al final' : 'Subir al inicio' }}
        </span>
      </button>
    </div>

    <div class="flex items-end gap-2 w-full">
      <div class="relative flex items-center flex-1">
        <label for="chat-message-input" class="sr-only">Mensaje</label>
        <textarea
          id="chat-message-input"
          ref="chatInputRef"
          :value="draftMessage"
          @input="emit('update:draftMessage', ($event.target as HTMLTextAreaElement).value)"
          :placeholder="
            isHitlRequired
              ? 'Introduce tus instrucciones de refinamiento...'
              : 'Escribe tu consulta...'
          "
          rows="3"
          class="w-full bg-[#030509] border rounded-xl pl-3.5 md:pl-4 pr-12 py-3 text-base sm:text-sm text-slate-200 focus:outline-none transition-all placeholder:text-[11px] placeholder-space-600 font-mono shadow-inner resize-none custom-scrollbar min-h-[76px] sm:min-h-[88px]"
          :class="
            isHitlRequired
              ? 'border-neon-amber/60 focus:border-neon-amber focus:ring-1 focus:ring-neon-amber/50'
              : 'border-space-700 focus:border-neon-cyan'
          "
          :disabled="isDebating && !isHitlRequired"
          @keydown="handleKeyDown"
        ></textarea>

        <button
          type="submit"
          data-test="chat-send-btn"
          :disabled="!draftMessage.trim() || (isDebating && !isHitlRequired)"
          class="absolute right-2.5 top-1/2 -translate-y-1/2 p-2 min-w-[36px] min-h-[36px] flex items-center justify-center bg-[#00e5ff] text-[#060a11] hover:bg-cyan-400 disabled:opacity-50 disabled:hover:bg-[#00e5ff] transition-all rounded-lg shadow-[0_0_10px_rgba(0,229,255,0.3)] cursor-pointer"
          :title="isHitlRequired ? 'Enviar refinamiento' : 'Enviar mensaje'"
        >
          <SendHorizontal class="w-4 h-4 md:w-5 md:h-5" />
        </button>
      </div>
    </div>
  </form>
</template>

