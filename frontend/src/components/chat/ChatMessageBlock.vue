<script setup lang="ts">
import { computed } from 'vue'
import {
  Check,
  Code2,
  Copy,
  Download,
  Eye,
  FileText,
  ImageIcon,
  Network,
  Printer,
} from '@lucide/vue'
import type { RenderedMessageBlock } from '../../composables/useChatArtifacts'
import ChatPresentationCard from './ChatPresentationCard.vue'
import type { ArtifactCopyPayload, ArtifactDownloadPayload, ArtifactOpenPayload } from './types'

const props = defineProps<{
  block: RenderedMessageBlock
  messageIndex: number
  blockIndex: number
  agentName?: string
  copiedDiagramIndex: number | null
  copiedCodeIndex: number | null
  copiedDocIndex: number | null
  copiedPresentationIndex: number | null
  activePresentationDownloadMenu: number | null
}>()

const emit = defineEmits<{
  (e: 'copy', payload: ArtifactCopyPayload): void
  (e: 'open', payload: ArtifactOpenPayload): void
  (e: 'download', payload: ArtifactDownloadPayload): void
  (e: 'toggle-presentation-download', cardKey: number): void
}>()

const cardKey = computed(() => props.messageIndex * 100 + props.blockIndex)
</script>

<template>
  <!-- Text block -->
  <div
    v-if="block.type === 'text'"
    class="whitespace-pre-wrap leading-relaxed break-words [overflow-wrap:break-word] min-w-0 max-w-full"
  >
    {{ block.content }}
  </div>

  <!-- Mermaid Diagram Card -->
  <div
    v-else-if="block.type === 'mermaid'"
    data-test="chat-diagram-card"
    class="my-2 bg-[#050a14] border border-cyan-500/40 rounded-xl overflow-hidden shadow-[0_0_20px_rgba(0,229,255,0.1)]"
  >
    <div class="flex items-center justify-between px-3.5 py-2 bg-[#081120] border-b border-cyan-500/30">
      <div class="flex items-center gap-2">
        <Network class="w-3.5 h-3.5 text-neon-cyan" />
        <span class="text-xs font-mono font-bold text-neon-cyan uppercase tracking-wider select-none">
          Diagrama
        </span>
      </div>

      <div class="flex items-center gap-2">
        <button
          type="button"
          @click="emit('copy', { kind: 'diagram', content: block.content, cardKey })"
          data-test="chat-diagram-copy-btn"
          class="relative group p-1.5 rounded-lg bg-[#030509] border border-cyan-500/40 hover:border-neon-cyan text-cyan-200 hover:text-white transition-colors cursor-pointer flex items-center justify-center"
          :title="copiedDiagramIndex === cardKey ? 'Copiado' : 'Copiar al portapapeles'"
          :aria-label="copiedDiagramIndex === cardKey ? 'Copiado' : 'Copiar al portapapeles'"
        >
          <Check v-if="copiedDiagramIndex === cardKey" class="w-3.5 h-3.5 text-emerald-400" />
          <Copy v-else class="w-3.5 h-3.5" />
          <span
            class="pointer-events-none absolute top-full mt-1.5 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono text-cyan-200 border border-cyan-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
          >
            {{ copiedDiagramIndex === cardKey ? 'Copiado' : 'Copiar' }}
          </span>
        </button>

        <button
          type="button"
          @click="
            emit('open', {
              kind: 'diagram',
              code: block.content,
              title: `Diagrama de ${agentName || 'Arquitectura'}`,
            })
          "
          data-test="chat-diagram-view-btn"
          class="relative group p-1.5 rounded-lg bg-neon-cyan/15 hover:bg-neon-cyan/25 border border-neon-cyan text-neon-cyan shadow-[0_0_10px_rgba(0,229,255,0.2)] transition-all cursor-pointer flex items-center justify-center"
          title="Ver diagrama"
          aria-label="Ver diagrama"
        >
          <Eye class="w-3.5 h-3.5" />
          <span
            class="pointer-events-none absolute top-full mt-1.5 right-0 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono font-bold text-neon-cyan border border-neon-cyan/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
          >
            Ver
          </span>
        </button>
      </div>
    </div>

    <pre class="p-3.5 bg-[#020408] font-mono text-xs text-cyan-200/90 overflow-x-auto custom-scrollbar max-h-48 border-t border-space-900/50"><code>{{ block.content }}</code></pre>
  </div>

  <!-- Code Block Card -->
  <div
    v-else-if="block.type === 'code'"
    data-test="chat-code-card"
    class="my-2 bg-[#050a14] border border-cyan-500/30 rounded-xl overflow-hidden shadow-[0_0_20px_rgba(0,229,255,0.08)]"
  >
    <div class="flex items-center justify-between px-3.5 py-2 bg-[#081120] border-b border-cyan-500/30">
      <div class="flex items-center gap-2">
        <Code2 class="w-3.5 h-3.5 text-neon-cyan" />
        <span class="text-xs font-mono font-bold text-neon-cyan uppercase tracking-wider select-none">
          Código
        </span>
      </div>

      <div class="flex items-center gap-2">
        <button
          type="button"
          @click="emit('copy', { kind: 'code', content: block.content, cardKey })"
          data-test="chat-code-copy-btn"
          class="relative group p-1.5 rounded-lg bg-[#030509] border border-cyan-500/40 hover:border-neon-cyan text-cyan-200 hover:text-white transition-colors cursor-pointer flex items-center justify-center"
          :title="copiedCodeIndex === cardKey ? 'Copiado' : 'Copiar al portapapeles'"
          :aria-label="copiedCodeIndex === cardKey ? 'Copiado' : 'Copiar al portapapeles'"
        >
          <Check v-if="copiedCodeIndex === cardKey" class="w-3.5 h-3.5 text-emerald-400" />
          <Copy v-else class="w-3.5 h-3.5" />
          <span
            class="pointer-events-none absolute top-full mt-1.5 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono text-cyan-200 border border-cyan-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
          >
            {{ copiedCodeIndex === cardKey ? 'Copiado' : 'Copiar' }}
          </span>
        </button>

        <button
          type="button"
          @click="
            emit('download', {
              kind: 'code',
              code: block.content,
              extension: block.extension,
              title: `codigo_${agentName || 'desarrollo'}`,
            })
          "
          data-test="chat-code-download-btn"
          class="relative group p-1.5 rounded-lg bg-[#030509] border border-cyan-500/40 hover:border-neon-cyan text-cyan-200 hover:text-white transition-colors cursor-pointer flex items-center justify-center"
          title="Descargar archivo"
          aria-label="Descargar archivo"
        >
          <Download class="w-3.5 h-3.5" />
          <span
            class="pointer-events-none absolute top-full mt-1.5 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono text-cyan-200 border border-cyan-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
          >
            Descargar
          </span>
        </button>

        <button
          type="button"
          @click="
            emit('open', {
              kind: 'code',
              code: block.content,
              language: block.language,
              extension: block.extension,
              title: `Código de ${agentName || 'Desarrollo'}`,
            })
          "
          data-test="chat-code-view-btn"
          class="relative group p-1.5 rounded-lg bg-neon-cyan/15 hover:bg-neon-cyan/25 border border-neon-cyan text-neon-cyan shadow-[0_0_10px_rgba(0,229,255,0.2)] transition-all cursor-pointer flex items-center justify-center"
          title="Abrir en pantalla completa"
          aria-label="Abrir en pantalla completa"
        >
          <Eye class="w-3.5 h-3.5" />
          <span
            class="pointer-events-none absolute top-full mt-1.5 right-0 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono font-bold text-neon-cyan border border-neon-cyan/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
          >
            Ver
          </span>
        </button>
      </div>
    </div>

    <pre class="p-3.5 bg-[#020408] font-mono text-xs text-cyan-100 overflow-x-auto custom-scrollbar max-h-48 border-t border-space-900/50"><code>{{ block.content }}</code></pre>
  </div>

  <!-- Image Card -->
  <div
    v-else-if="block.type === 'image'"
    data-test="chat-image-card"
    class="my-2 bg-[#050a14] border border-pink-500/30 rounded-xl overflow-hidden shadow-[0_0_20px_rgba(236,72,153,0.1)]"
  >
    <div class="flex items-center justify-between px-3.5 py-2 bg-[#120818] border-b border-pink-500/30">
      <div class="flex items-center gap-2">
        <ImageIcon class="w-3.5 h-3.5 text-pink-400" />
        <span class="text-xs font-mono font-bold text-pink-400 uppercase tracking-wider select-none">
          Imágenes
        </span>
      </div>

      <div class="flex items-center gap-2">
        <button
          type="button"
          @click="
            emit('download', {
              kind: 'image',
              imageUrl: block.content,
              title: block.alt || 'recurso',
            })
          "
          data-test="chat-image-download-btn"
          class="relative group p-1.5 rounded-lg bg-[#030509] border border-pink-500/40 hover:border-pink-400 text-pink-200 hover:text-white transition-colors cursor-pointer flex items-center justify-center"
          title="Descargar imagen"
          aria-label="Descargar imagen"
        >
          <Download class="w-3.5 h-3.5" />
          <span
            class="pointer-events-none absolute top-full mt-1.5 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono text-pink-300 border border-pink-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
          >
            Descargar
          </span>
        </button>

        <button
          type="button"
          @click="
            emit('open', {
              kind: 'image',
              imageUrl: block.content,
              alt: block.alt,
              title: `Recurso de ${agentName || 'Diseño'}`,
            })
          "
          data-test="chat-image-view-btn"
          class="relative group p-1.5 rounded-lg bg-pink-500/15 hover:bg-pink-500/25 border border-pink-500 text-pink-300 shadow-[0_0_10px_rgba(236,72,153,0.2)] transition-all cursor-pointer flex items-center justify-center"
          title="Ver en pantalla completa"
          aria-label="Ver en pantalla completa"
        >
          <Eye class="w-3.5 h-3.5" />
          <span
            class="pointer-events-none absolute top-full mt-1.5 right-0 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono font-bold text-pink-300 border border-pink-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
          >
            Ver
          </span>
        </button>
      </div>
    </div>

    <div class="p-3 bg-[#020408] flex items-center justify-center border-t border-space-900/50">
      <button
        type="button"
        class="p-0 bg-transparent border-0 cursor-pointer rounded overflow-hidden focus:outline-none focus:ring-2 focus:ring-pink-500 max-h-60 flex items-center justify-center"
        :aria-label="`Ver imagen: ${block.alt || 'Recurso visual'}`"
        @click="
          emit('open', {
            kind: 'image',
            imageUrl: block.content,
            alt: block.alt,
            title: `Recurso de ${agentName || 'Diseño'}`,
          })
        "
      >
        <img
          :src="block.content"
          :alt="block.alt"
          data-test="chat-image-preview"
          class="max-h-60 rounded object-contain hover:opacity-95 transition-opacity"
        />
      </button>
    </div>
  </div>

  <!-- Document Card -->
  <div
    v-else-if="block.type === 'document'"
    data-test="chat-document-card"
    class="my-2 bg-[#050a14] border border-pink-500/40 rounded-xl overflow-hidden shadow-[0_0_20px_rgba(236,72,153,0.12)]"
  >
    <div class="flex items-center justify-between px-3.5 py-2 bg-[#0e0816] border-b border-pink-500/30">
      <div class="flex items-center gap-2 min-w-0">
        <FileText class="w-3.5 h-3.5 text-pink-400 shrink-0" />
        <span class="text-xs font-mono font-bold text-pink-400 uppercase tracking-wider select-none">
          Documento
        </span>
      </div>

      <div class="flex items-center gap-1.5 shrink-0">
        <button
          type="button"
          @click="emit('copy', { kind: 'document', content: block.content, cardKey })"
          data-test="chat-doc-copy-btn"
          class="relative group p-1.5 rounded-lg bg-[#030509] border border-pink-500/40 hover:border-pink-400 text-pink-200 hover:text-white transition-colors cursor-pointer flex items-center justify-center"
          :title="copiedDocIndex === cardKey ? 'Copiado' : 'Copiar Markdown al portapapeles'"
          :aria-label="copiedDocIndex === cardKey ? 'Copiado' : 'Copiar Markdown al portapapeles'"
        >
          <Check v-if="copiedDocIndex === cardKey" class="w-3.5 h-3.5 text-emerald-400" />
          <Copy v-else class="w-3.5 h-3.5" />
          <span
            class="pointer-events-none absolute top-full mt-1.5 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono text-pink-300 border border-pink-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
          >
            {{ copiedDocIndex === cardKey ? 'Copiado' : 'Copiar' }}
          </span>
        </button>

        <button
          type="button"
          @click="
            emit('download', {
              kind: 'document-md',
              content: block.content,
              title: block.title || 'documento',
            })
          "
          data-test="chat-doc-download-md-btn"
          class="relative group p-1.5 rounded-lg bg-[#030509] border border-pink-500/40 hover:border-pink-400 text-pink-200 hover:text-white transition-colors cursor-pointer flex items-center justify-center"
          title="Descargar archivo Markdown (.md)"
          aria-label="Descargar archivo Markdown (.md)"
        >
          <Download class="w-3.5 h-3.5" />
          <span
            class="pointer-events-none absolute top-full mt-1.5 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono font-bold text-pink-300 border border-pink-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
          >
            Descargar .md
          </span>
        </button>

        <button
          type="button"
          @click="
            emit('download', {
              kind: 'document-pdf',
              content: block.content,
              title: block.title || 'documento',
            })
          "
          data-test="chat-doc-export-pdf-btn"
          class="relative group p-1.5 rounded-lg bg-pink-500/15 hover:bg-pink-500/25 border border-pink-500 text-pink-300 transition-colors cursor-pointer flex items-center justify-center"
          title="Descargar / Imprimir en PDF"
          aria-label="Descargar / Imprimir en PDF"
        >
          <Printer class="w-3.5 h-3.5" />
          <span
            class="pointer-events-none absolute top-full mt-1.5 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono font-bold text-pink-300 border border-pink-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
          >
            Descargar .pdf
          </span>
        </button>

        <button
          type="button"
          @click="
            emit('open', {
              kind: 'document',
              content: block.content,
              title: block.title || 'Documento Técnico',
            })
          "
          data-test="chat-doc-view-btn"
          class="relative group p-1.5 rounded-lg bg-pink-500/15 hover:bg-pink-500/25 border border-pink-500 text-pink-300 shadow-[0_0_10px_rgba(236,72,153,0.2)] transition-all cursor-pointer flex items-center justify-center"
          title="Ver Documento en pantalla completa"
          aria-label="Ver Documento en pantalla completa"
        >
          <Eye class="w-3.5 h-3.5" />
          <span
            class="pointer-events-none absolute top-full mt-1.5 right-0 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono font-bold text-pink-300 border border-pink-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
          >
            Ver
          </span>
        </button>
      </div>
    </div>

    <div class="p-4 bg-[#02050a] text-slate-200 text-xs leading-relaxed max-h-56 overflow-y-auto custom-scrollbar border-t border-space-900/50 selection:bg-pink-500/30">
      <div class="doc-body font-sans max-w-none" v-html="block.renderedHtml || ''"></div>
    </div>
  </div>

  <!-- Presentation Block Card -->
  <ChatPresentationCard
    v-else-if="block.type === 'presentation'"
    :block="block"
    :card-key="cardKey"
    :agent-name="agentName"
    :is-copied="copiedPresentationIndex === cardKey"
    :is-download-menu-open="activePresentationDownloadMenu === cardKey"
    @copy="emit('copy', $event)"
    @open="emit('open', $event)"
    @download="emit('download', $event)"
    @toggle-download="emit('toggle-presentation-download', $event)"
  />
</template>
