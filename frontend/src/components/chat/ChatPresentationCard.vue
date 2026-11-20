<script setup lang="ts">
import {
  Check,
  ChevronDown,
  Copy,
  Download,
  Eye,
  FileCode,
  Globe,
  MonitorPlay,
} from '@lucide/vue'
import type { RenderedMessageBlock } from '../../composables/useChatArtifacts'
import type { ArtifactCopyPayload, ArtifactDownloadPayload, ArtifactOpenPayload } from './types'

defineProps<{
  block: RenderedMessageBlock
  cardKey: number
  agentName?: string
  isCopied: boolean
  isDownloadMenuOpen: boolean
}>()

const emit = defineEmits<{
  (e: 'copy', payload: ArtifactCopyPayload): void
  (e: 'open', payload: ArtifactOpenPayload): void
  (e: 'download', payload: ArtifactDownloadPayload): void
  (e: 'toggle-download', cardKey: number): void
}>()
</script>

<template>
  <div
    data-test="chat-presentation-card"
    class="my-2 bg-[#050a14] border border-cyan-500/40 rounded-xl overflow-hidden shadow-[0_0_20px_rgba(0,229,255,0.12)]"
  >
    <div class="flex items-center justify-between px-3.5 py-2 bg-[#081120] border-b border-cyan-500/30">
      <div class="flex items-center gap-2 min-w-0">
        <MonitorPlay class="w-3.5 h-3.5 text-neon-cyan shrink-0" />
        <span class="text-xs font-mono font-bold text-neon-cyan uppercase tracking-wider select-none">
          Presentación
        </span>
      </div>

      <div class="flex items-center gap-1.5 shrink-0">
        <button
          type="button"
          @click="emit('copy', { kind: 'presentation', content: block.content, cardKey })"
          data-test="chat-presentation-copy-btn"
          class="relative group p-1.5 rounded-lg bg-[#030509] border border-cyan-500/40 hover:border-cyan-400 text-cyan-200 hover:text-white transition-colors cursor-pointer flex items-center justify-center"
          :title="isCopied ? 'Copiado' : 'Copiar al portapapeles'"
          :aria-label="isCopied ? 'Copiado' : 'Copiar al portapapeles'"
        >
          <Check v-if="isCopied" class="w-3.5 h-3.5 text-emerald-400" />
          <Copy v-else class="w-3.5 h-3.5" />
          <span
            class="pointer-events-none absolute top-full mt-1.5 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono text-cyan-200 border border-cyan-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
          >
            {{ isCopied ? 'Copiado' : 'Copiar' }}
          </span>
        </button>

        <div class="relative">
          <button
            type="button"
            @click.stop="emit('toggle-download', cardKey)"
            data-test="chat-presentation-download-btn"
            class="relative group p-1.5 rounded-lg bg-[#030509] border border-cyan-500/40 hover:border-cyan-400 text-cyan-200 hover:text-white transition-colors cursor-pointer flex items-center gap-1"
            title="Descargar presentación"
            aria-label="Descargar presentación"
            :aria-expanded="isDownloadMenuOpen"
          >
            <Download class="w-3.5 h-3.5" />
            <ChevronDown
              class="w-2.5 h-2.5 opacity-70 transition-transform duration-150"
              :class="isDownloadMenuOpen ? 'rotate-180' : ''"
            />
            <span
              v-if="!isDownloadMenuOpen"
              class="pointer-events-none absolute top-full mt-1.5 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono font-bold text-cyan-200 border border-cyan-500/40 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
            >
              Descargar
            </span>
          </button>

          <div
            v-if="isDownloadMenuOpen"
            data-test="chat-presentation-download-dropdown"
            class="absolute right-0 top-full mt-1.5 w-48 bg-[#050b18]/95 border border-cyan-500/40 rounded-xl p-1 shadow-[0_0_20px_rgba(0,229,255,0.25)] backdrop-blur-md z-50 flex flex-col gap-0.5 font-mono text-left animate-in fade-in duration-100"
          >
            <button
              type="button"
              @click="
                emit('download', {
                  kind: 'presentation-pptx',
                  content: block.content,
                  title: block.title,
                })
              "
              data-test="chat-presentation-download-pptx-btn"
              class="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-slate-200 hover:text-white hover:bg-cyan-950/60 transition-colors text-xs cursor-pointer text-left"
            >
              <MonitorPlay class="w-3.5 h-3.5 text-cyan-400 shrink-0" />
              <span>PowerPoint (.pptx)</span>
            </button>
            <button
              type="button"
              @click="
                emit('download', {
                  kind: 'presentation-html',
                  content: block.content,
                  title: block.title,
                })
              "
              data-test="chat-presentation-download-html-btn"
              class="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-slate-200 hover:text-white hover:bg-cyan-950/60 transition-colors text-xs cursor-pointer text-left"
            >
              <Globe class="w-3.5 h-3.5 text-cyan-400 shrink-0" />
              <span>Web (.html)</span>
            </button>
            <button
              type="button"
              @click="
                emit('download', {
                  kind: 'presentation-md',
                  content: block.content,
                  title: block.title,
                })
              "
              data-test="chat-presentation-download-md-btn"
              class="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-slate-200 hover:text-white hover:bg-cyan-950/60 transition-colors text-xs cursor-pointer text-left"
            >
              <FileCode class="w-3.5 h-3.5 text-cyan-400 shrink-0" />
              <span>Markdown (.md)</span>
            </button>
          </div>
        </div>

        <button
          type="button"
          @click="
            emit('open', {
              kind: 'presentation',
              content: block.content,
              title: block.title || `Presentación de ${agentName || 'Atenea'}`,
            })
          "
          data-test="chat-presentation-view-btn"
          class="relative group p-1.5 rounded-lg bg-neon-cyan/15 hover:bg-neon-cyan/25 border border-neon-cyan text-neon-cyan shadow-[0_0_10px_rgba(0,229,255,0.2)] transition-all cursor-pointer flex items-center justify-center"
          title="Ver Presentación de Diapositivas"
          aria-label="Ver Presentación de Diapositivas"
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

    <div class="p-4 bg-[#02050a] flex items-center justify-between gap-4 border-t border-space-900/50">
      <div class="min-w-0">
        <div class="text-xs font-mono font-bold text-white uppercase truncate">
          {{ block.title || 'Presentación de Diapositivas' }}
        </div>
        <div class="text-[11px] font-mono text-cyan-400/80 mt-0.5">
          {{
            block.slideCount
              ? `${block.slideCount} diapositivas listas para proyectar`
              : 'Diapositivas interactivas 16:9'
          }}
        </div>
      </div>
      <button
        type="button"
        @click="
          emit('open', {
            kind: 'presentation',
            content: block.content,
            title: block.title || `Presentación de ${agentName || 'Atenea'}`,
          })
        "
        data-test="chat-presentation-project-btn"
        class="px-3 py-1.5 rounded-lg bg-neon-cyan/10 hover:bg-neon-cyan/20 border border-neon-cyan/50 text-neon-cyan font-mono text-xs flex items-center gap-1.5 transition-colors cursor-pointer shrink-0"
      >
        <MonitorPlay class="w-3.5 h-3.5" />
        <span>Proyectar</span>
      </button>
    </div>
  </div>
</template>

