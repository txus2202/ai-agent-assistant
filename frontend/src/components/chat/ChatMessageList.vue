<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { Bot, Info, Square, X } from '@lucide/vue'
import type { RenderedMessageBlock } from '../../composables/useChatArtifacts'
import type { ChatMessage } from '../../utils/debateHelpers'
import ChatMessageItem from './ChatMessageItem.vue'
import type { ArtifactCopyPayload, ArtifactDownloadPayload, ArtifactOpenPayload } from './types'

const props = defineProps<{
  messages: ChatMessage[]
  memoizedMessageBlocks: RenderedMessageBlock[][]
  isDebating: boolean
  isTtsPlaying: boolean
  projectName: string
  copiedDiagramIndex: number | null
  copiedCodeIndex: number | null
  copiedDocIndex: number | null
  copiedPresentationIndex: number | null
  activePresentationDownloadMenu: number | null
}>()

const emit = defineEmits<{
  (e: 'stop-tts'): void
  (e: 'cancel-debate'): void
  (e: 'scroll-state-change', payload: { isScrollable: boolean; direction: 'up' | 'down' }): void
  (e: 'copy', payload: ArtifactCopyPayload): void
  (e: 'open', payload: ArtifactOpenPayload): void
  (e: 'download', payload: ArtifactDownloadPayload): void
  (e: 'toggle-presentation-download', cardKey: number): void
}>()

const chatScroll = ref<HTMLElement | null>(null)
const isChatScrollable = ref(false)
const scrollDirection = ref<'up' | 'down'>('up')
const showCancelInfo = ref(false)
const cancelInfoRef = ref<HTMLElement | null>(null)
let scrollResizeObserver: ResizeObserver | null = null

const updateChatScrollState = () => {
  const el = chatScroll.value
  if (!el) {
    isChatScrollable.value = false
    emit('scroll-state-change', { isScrollable: false, direction: scrollDirection.value })
    return
  }
  const maxScroll = el.scrollHeight - el.clientHeight
  const canScroll = maxScroll > 15
  isChatScrollable.value = canScroll

  if (canScroll) {
    scrollDirection.value = el.scrollTop < maxScroll / 2 ? 'down' : 'up'
  }
  emit('scroll-state-change', { isScrollable: canScroll, direction: scrollDirection.value })
}

const toggleScroll = () => {
  const el = chatScroll.value
  if (!el) return
  if (scrollDirection.value === 'down') {
    if (typeof el.scrollTo === 'function') {
      el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
    } else {
      el.scrollTop = el.scrollHeight
    }
  } else if (typeof el.scrollTo === 'function') {
    el.scrollTo({ top: 0, behavior: 'smooth' })
  } else {
    el.scrollTop = 0
  }
}

const toggleCancelInfo = () => {
  showCancelInfo.value = !showCancelInfo.value
}

const handleCancelDebate = () => {
  emit('cancel-debate')
  showCancelInfo.value = false
}

const handleClickOutsideCancelInfo = (event: MouseEvent) => {
  if (!cancelInfoRef.value || !showCancelInfo.value) return
  const path = event.composedPath()
  if (!path.includes(cancelInfoRef.value)) {
    showCancelInfo.value = false
  }
}

watch(
  () => props.messages.length,
  async (newLen) => {
    await nextTick()
    updateChatScrollState()
    if (chatScroll.value && newLen > 0) {
      const messageBlocks = chatScroll.value.querySelectorAll('.message-block')
      if (messageBlocks.length > 0) {
        const lastMessageEl = messageBlocks[messageBlocks.length - 1] as HTMLElement
        lastMessageEl.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }
    }
  },
)

watch(
  () => props.isDebating,
  async () => {
    await nextTick()
    updateChatScrollState()
  },
)

onMounted(() => {
  document.addEventListener('click', handleClickOutsideCancelInfo)
  window.addEventListener('resize', updateChatScrollState)
  void nextTick(() => {
    updateChatScrollState()
    if (typeof ResizeObserver !== 'undefined' && chatScroll.value) {
      scrollResizeObserver = new ResizeObserver(() => {
        updateChatScrollState()
      })
      scrollResizeObserver.observe(chatScroll.value)
      if (chatScroll.value.firstElementChild) {
        scrollResizeObserver.observe(chatScroll.value.firstElementChild)
      }
    }
  })
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutsideCancelInfo)
  window.removeEventListener('resize', updateChatScrollState)
  scrollResizeObserver?.disconnect()
  scrollResizeObserver = null
})

defineExpose({
  toggleScroll,
  updateChatScrollState,
})
</script>

<template>
  <div
    ref="chatScroll"
    data-test="chat-messages-scroll"
    @scroll.passive="updateChatScrollState"
    class="flex-1 overflow-y-auto overflow-x-hidden custom-scrollbar p-3.5 md:px-4 md:py-5 space-y-6 min-w-0 max-w-full"
  >
    <ChatMessageItem
      v-for="(msg, i) in messages"
      :key="msg.id ?? i"
      :message="msg"
      :message-index="i"
      :is-last-message="i === messages.length - 1"
      :project-name="projectName"
      :is-tts-playing="isTtsPlaying"
      :blocks="memoizedMessageBlocks[i] ?? []"
      :copied-diagram-index="copiedDiagramIndex"
      :copied-code-index="copiedCodeIndex"
      :copied-doc-index="copiedDocIndex"
      :copied-presentation-index="copiedPresentationIndex"
      :active-presentation-download-menu="activePresentationDownloadMenu"
      @stop-tts="emit('stop-tts')"
      @copy="emit('copy', $event)"
      @open="emit('open', $event)"
      @download="emit('download', $event)"
      @toggle-presentation-download="emit('toggle-presentation-download', $event)"
    />

    <!-- Typing indicator -->
    <div v-if="isDebating" class="flex flex-col items-start max-w-[90%] relative" data-test="typing-indicator">
      <div class="flex items-center space-x-2 mb-2">
        <div
          class="w-5 h-5 rounded-full border border-neon-green/50 flex items-center justify-center bg-neon-green/10 text-neon-green"
        >
          <Bot class="w-3 h-3" />
        </div>
        <span class="text-[11px] font-bold text-white tracking-widest font-mono">
          {{ projectName }}
        </span>

        <button
          type="button"
          @click="handleCancelDebate"
          class="px-2 py-0.5 bg-red-950/40 hover:bg-red-900/80 border border-red-500/50 hover:border-red-400 text-red-300 hover:text-white text-[9px] font-mono uppercase tracking-widest rounded shadow-sm flex items-center space-x-1.5 transition-all cursor-pointer active:scale-95"
          title="Cancelar deliberación del agente en curso"
          data-test="cancel-debate-btn"
        >
          <Square class="w-2.5 h-2.5 fill-red-400 text-red-400" />
          <span>Cancelar</span>
        </button>

        <div ref="cancelInfoRef" class="relative inline-flex items-center">
          <button
            type="button"
            @click.stop="toggleCancelInfo"
            class="p-0.5 text-slate-400 hover:text-cyan-300 transition-colors cursor-pointer rounded hover:bg-space-800/60"
            :class="{ 'text-cyan-300 bg-space-800': showCancelInfo }"
            title="Información sobre la cancelación"
            data-test="cancel-info-toggle-btn"
          >
            <Info class="w-3.5 h-3.5" />
          </button>

          <div
            v-if="showCancelInfo"
            class="absolute left-6 top-0 z-50 w-64 p-2.5 bg-space-900 border border-cyan-500/40 rounded-lg shadow-[0_4px_20px_rgba(0,0,0,0.5)] text-slate-300 text-[11px] font-sans leading-normal animate-fade-in"
            data-test="cancel-info-popover"
          >
            <div class="flex items-start justify-between gap-1 mb-1">
              <span class="font-mono text-[10px] text-cyan-300 font-bold uppercase tracking-wider">
                Cancelar agente
              </span>
              <button
                type="button"
                @click.stop="showCancelInfo = false"
                class="text-space-400 hover:text-white p-0.5 rounded cursor-pointer"
                data-test="cancel-info-close-btn"
              >
                <X class="w-3 h-3" />
              </button>
            </div>
            <p class="text-slate-300 text-[10px]">
              Cancela la ejecución de los agentes en curso inmediatamente si la respuesta se demora o
              deseas reformular tu consulta sin tener que recargar la página (F5).
            </p>
          </div>
        </div>
      </div>
      <div
        class="bg-[#030509] border border-neon-green/40 rounded-xl rounded-tl-none px-5 py-3 shadow-[0_0_15px_-3px_rgba(0,255,157,0.1)]"
      >
        <div class="flex space-x-1 items-center h-4">
          <div class="w-1.5 h-1.5 bg-neon-green rounded-full animate-bounce"></div>
          <div class="w-1.5 h-1.5 bg-neon-green rounded-full animate-bounce" style="animation-delay: 0.2s"></div>
          <div class="w-1.5 h-1.5 bg-neon-green rounded-full animate-bounce" style="animation-delay: 0.4s"></div>
        </div>
      </div>
    </div>
  </div>
</template>

