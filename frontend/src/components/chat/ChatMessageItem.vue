<script setup lang="ts">
import { Bot, User } from '@lucide/vue'
import type { RenderedMessageBlock } from '../../composables/useChatArtifacts'
import type { ChatMessage } from '../../utils/debateHelpers'
import ChatMessageBlock from './ChatMessageBlock.vue'
import type { ArtifactCopyPayload, ArtifactDownloadPayload, ArtifactOpenPayload } from './types'

defineProps<{
  message: ChatMessage
  messageIndex: number
  isLastMessage: boolean
  projectName: string
  isTtsPlaying: boolean
  blocks: RenderedMessageBlock[]
  copiedDiagramIndex: number | null
  copiedCodeIndex: number | null
  copiedDocIndex: number | null
  copiedPresentationIndex: number | null
  activeDocumentDownloadMenu?: number | null
  activePresentationDownloadMenu: number | null
}>()

const emit = defineEmits<{
  (e: 'stop-tts'): void
  (e: 'copy', payload: ArtifactCopyPayload): void
  (e: 'open', payload: ArtifactOpenPayload): void
  (e: 'download', payload: ArtifactDownloadPayload): void
  (e: 'toggle-document-download', cardKey: number): void
  (e: 'toggle-presentation-download', cardKey: number): void
}>()
</script>

<template>
  <div class="flex flex-col w-full message-block min-w-0 max-w-full">
    <!-- User Bubble -->
    <div v-if="message.role === 'user'" class="flex flex-col items-end max-w-[85%] self-end min-w-0">
      <div class="flex items-center space-x-2 mb-2 text-neon-cyan">
        <span class="text-[10px] font-mono tracking-wider uppercase font-bold">USUARIO (TÚ)</span>
        <User class="w-3.5 h-3.5" />
      </div>
      <div
        class="bg-[#0a192f] border border-neon-cyan/50 rounded-xl rounded-tr-none px-4 py-3 sm:px-5 sm:py-4 text-sm text-cyan-50 shadow-[0_0_15px_-3px_rgba(0,229,255,0.15)] leading-relaxed break-words [overflow-wrap:break-word] min-w-0 max-w-full overflow-hidden"
      >
        {{ message.content }}
      </div>
    </div>

    <!-- Assistant Bubble -->
    <div v-else class="flex flex-col items-start max-w-[95%] min-w-0 w-full">
      <div class="flex items-center space-x-2 mb-2">
        <div
          class="w-5 h-5 rounded-full border flex items-center justify-center transition-colors"
          :style="
            message.colorHex
              ? {
                  borderColor: `${message.colorHex}80`,
                  backgroundColor: `${message.colorHex}1a`,
                  color: message.colorHex,
                }
              : {}
          "
          :class="!message.colorHex ? 'border-neon-green/50 bg-neon-green/10 text-neon-green' : ''"
        >
          <Bot class="w-3 h-3" />
        </div>
        <span class="text-[11px] font-bold text-white tracking-widest font-mono">
          {{ projectName }}
        </span>
        <span
          class="px-2 py-0.5 border text-[8px] font-mono uppercase tracking-widest rounded shadow-sm transition-colors"
          :style="
            message.colorHex
              ? {
                  borderColor: `${message.colorHex}4d`,
                  backgroundColor: `${message.colorHex}1a`,
                  color: message.colorHex,
                }
              : {}
          "
          :class="!message.colorHex ? 'bg-neon-green/10 border-neon-green/30 text-neon-green' : ''"
        >
          {{ message.agentName || 'ATENEA' }}
        </span>

        <!-- Stop TTS Button -->
        <button
          v-if="isTtsPlaying && isLastMessage"
          type="button"
          @click="emit('stop-tts')"
          class="ml-2 px-2 py-0.5 bg-red-900/40 hover:bg-red-900/80 border border-red-500/50 text-red-400 text-[9px] font-mono uppercase tracking-widest rounded shadow-sm flex items-center space-x-1 transition-colors cursor-pointer"
          title="Detener lectura de este mensaje"
        >
          <div class="w-1.5 h-1.5 bg-red-500 rounded-sm"></div>
          <span>Silenciar</span>
        </button>
      </div>

      <div
        class="w-full bg-[#030509] border rounded-xl rounded-tl-none px-4 py-3 sm:px-5 sm:py-4 text-[13px] text-slate-300 leading-relaxed transition-colors flex flex-col gap-3 min-w-0 max-w-full overflow-hidden"
        :style="
          message.colorHex
            ? {
                borderColor: `${message.colorHex}4d`,
                boxShadow: `0 0 15px -3px ${message.colorHex}1a`,
              }
            : {}
        "
        :class="!message.colorHex ? 'border-neon-green/40 shadow-[0_0_15px_-3px_rgba(0,255,157,0.1)]' : ''"
      >
        <ChatMessageBlock
          v-for="(block, blockIdx) in blocks"
          :key="`${message.id ?? messageIndex}-${block.type}-${blockIdx}`"
          :block="block"
          :message-index="messageIndex"
          :block-index="blockIdx"
          :agent-name="message.agentName"
          :copied-diagram-index="copiedDiagramIndex"
          :copied-code-index="copiedCodeIndex"
          :copied-doc-index="copiedDocIndex"
          :copied-presentation-index="copiedPresentationIndex"
          :active-document-download-menu="activeDocumentDownloadMenu ?? null"
          :active-presentation-download-menu="activePresentationDownloadMenu"
          @copy="emit('copy', $event)"
          @open="emit('open', $event)"
          @download="emit('download', $event)"
          @toggle-document-download="emit('toggle-document-download', $event)"
          @toggle-presentation-download="emit('toggle-presentation-download', $event)"
        />
      </div>
    </div>
  </div>
</template>

