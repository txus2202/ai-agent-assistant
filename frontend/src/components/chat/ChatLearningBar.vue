<script setup lang="ts">
import { Brain, Check, X } from '@lucide/vue'

defineProps<{
  isLearningSession: boolean
  canLearn: boolean
  learningStatusMessage: string | null
  selectedFiles: File[]
}>()

const emit = defineEmits<{
  (e: 'learn-session'): void
  (e: 'clear-chat'): void
  (e: 'dismiss-learning-status'): void
  (e: 'clear-files'): void
  (e: 'remove-file', index: number): void
}>()
</script>

<template>
  <div class="p-3.5 md:px-4 md:py-5 border-b border-space-800/50 relative">
    <div class="flex justify-between items-center gap-2">
      <div class="min-w-0 flex items-center space-x-2">
        <div class="w-2 h-2 rounded-full bg-neon-cyan glow-cyan shrink-0"></div>
        <h2 class="font-bold text-white text-xs md:text-[13px] tracking-wider font-mono">
          CONVERSACIÓN
        </h2>
      </div>
      <div class="flex items-center space-x-1.5 md:space-x-2 shrink-0">
        <!-- Learn Button -->
        <button
          type="button"
          @click="emit('learn-session')"
          :disabled="!canLearn || isLearningSession"
          class="text-[9px] border border-cyan-800/80 hover:border-neon-cyan text-neon-cyan font-mono px-2.5 md:px-3 h-7 rounded transition-all uppercase tracking-widest bg-[#040e1a] hover:bg-neon-cyan/15 inline-flex items-center justify-center gap-1.5 leading-none disabled:opacity-40 disabled:cursor-not-allowed shadow-[0_0_10px_rgba(0,229,255,0.08)] cursor-pointer"
          title="Pedir a Metis que sintetice y aprenda la sesión en Obsidian Vault"
          data-test="learn-session-btn"
        >
          <Brain class="w-3.5 h-3.5 shrink-0" :class="{ 'animate-pulse': isLearningSession }" />
          <span class="leading-none">{{ isLearningSession ? 'Asimilando...' : 'Aprender' }}</span>
        </button>

        <!-- Clear Chat -->
        <button
          type="button"
          @click="emit('clear-chat')"
          class="text-[9px] border border-space-700 hover:border-space-500 text-space-400 hover:text-slate-300 font-mono px-2.5 md:px-3 h-7 rounded transition-colors uppercase tracking-widest bg-space-900 inline-flex items-center justify-center leading-none cursor-pointer"
        >
          <span class="leading-none">Limpiar</span>
        </button>
      </div>
    </div>

    <!-- Learning status notification banner -->
    <div
      v-if="learningStatusMessage"
      class="mt-3 bg-[#031525] border border-neon-cyan/40 rounded-lg p-3 flex items-center justify-between shadow-[0_0_15px_rgba(0,229,255,0.15)] text-xs font-mono text-cyan-200 animate-fade-in"
      data-test="learning-status-banner"
    >
      <div class="flex items-center space-x-2.5">
        <Brain class="w-4 h-4 text-neon-cyan shrink-0" />
        <span>{{ learningStatusMessage }}</span>
      </div>
      <button
        type="button"
        @click="emit('dismiss-learning-status')"
        class="text-space-400 hover:text-white p-1 rounded hover:bg-space-800 transition-colors cursor-pointer"
        title="Cerrar notificación"
      >
        <X class="w-3.5 h-3.5" />
      </button>
    </div>

    <!-- File attachments indicator -->
    <div
      v-if="selectedFiles.length > 0"
      class="mt-4 bg-[#0a192f] border border-neon-cyan/30 rounded-lg p-3 flex flex-col gap-2 shadow-inner"
      data-test="file-attachments-container"
    >
      <div class="flex items-center justify-between">
        <div class="flex items-center space-x-2">
          <Check class="w-4 h-4 text-neon-cyan shrink-0" />
          <span class="text-[11px] text-neon-cyan/90 font-mono font-bold tracking-wide">
            {{
              selectedFiles.length === 1
                ? `Archivo de contexto cargado (${selectedFiles[0]?.name})`
                : `${selectedFiles.length} archivos cargados para Metis`
            }}
          </span>
        </div>
        <button
          type="button"
          @click="emit('clear-files')"
          class="text-[9px] font-mono text-space-400 hover:text-red-400 uppercase tracking-wider transition-colors cursor-pointer"
          data-test="clear-files-btn"
        >
          Quitar todos
        </button>
      </div>

      <div class="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto custom-scrollbar pt-1">
        <div
          v-for="(file, index) in selectedFiles"
          :key="`${file.name}-${index}`"
          class="bg-[#030509] border border-neon-cyan/40 px-2 py-1 rounded text-[10px] font-mono text-cyan-200 flex items-center space-x-1.5 shadow-sm"
          data-test="attached-file-chip"
        >
          <span class="truncate max-w-[160px]">{{ file.name }}</span>
          <button
            type="button"
            @click="emit('remove-file', index)"
            class="text-space-400 hover:text-red-400 transition-colors cursor-pointer p-0.5 rounded hover:bg-space-800"
            title="Quitar archivo"
            data-test="remove-file-btn"
          >
            <X class="w-3 h-3" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

