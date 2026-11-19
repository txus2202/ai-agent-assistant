<script setup lang="ts">
import { Check, Edit3, GitFork, RotateCcw, Sparkles, Square, X } from '@lucide/vue'

export interface HitlSelectableAgent {
  value: string
  label: string
  colorHex: string
}

const props = defineProps<{
  selectableAgents: HitlSelectableAgent[]
  selectedTargets: string[]
  hasErrorRecovery: boolean
}>()

const emit = defineEmits<{
  (e: 'toggle-target', role: string): void
  (e: 'retry'): void
  (e: 'approve'): void
  (e: 'consolidate'): void
  (e: 'finish'): void
  (e: 'refine'): void
  (e: 'divert'): void
  (e: 'reject'): void
}>()

const isSelected = (role: string) => props.selectedTargets.includes(role)
</script>

<template>
  <div
    data-test="hitl-chat-card"
    class="mb-3 p-3.5 bg-[#080d1a] border border-neon-amber/60 rounded-xl shadow-[0_0_20px_rgba(245,158,11,0.15)] flex flex-col gap-2.5 animate-fade-in"
  >
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <span class="w-2 h-2 rounded-full bg-neon-amber animate-pulse"></span>
        <span class="text-xs font-mono font-bold text-neon-amber tracking-wider uppercase">
          Punto de Control (HITL)
        </span>
      </div>
      <button
        type="button"
        @click="emit('retry')"
        data-test="hitl-retry-btn"
        class="p-1.5 rounded-lg border transition-all flex items-center justify-center cursor-pointer group"
        :class="
          hasErrorRecovery
            ? 'bg-amber-500/20 hover:bg-amber-500/35 border-amber-400 text-amber-300 ring-2 ring-amber-400/30 animate-pulse'
            : 'bg-space-800/60 hover:bg-space-700/80 border-space-700/80 text-slate-400 hover:text-amber-400 hover:border-amber-500/40'
        "
        title="Reintentar ejecución de fase"
        aria-label="Reintentar ejecución de fase"
      >
        <RotateCcw class="w-3.5 h-3.5 transition-transform group-hover:-rotate-90" />
      </button>
    </div>

    <!-- Target Agents Chips Selector -->
    <div v-if="selectableAgents.length > 0" class="flex flex-col gap-1.5 pt-1">
      <span class="text-[10px] font-mono text-slate-400">
        Redirigir a agentes específicos (opcional):
      </span>
      <div class="flex flex-wrap gap-1.5">
        <button
          v-for="agent in selectableAgents"
          :key="agent.value"
          type="button"
          @click="emit('toggle-target', agent.value)"
          data-test="hitl-target-chip"
          class="px-2 py-0.5 rounded text-[10px] font-mono border transition-all flex items-center gap-1.5 cursor-pointer"
          :style="
            isSelected(agent.value)
              ? {
                  borderColor: agent.colorHex,
                  backgroundColor: `${agent.colorHex}25`,
                  color: '#ffffff',
                }
              : {
                  borderColor: `${agent.colorHex}40`,
                  backgroundColor: 'transparent',
                  color: '#94a3b8',
                }
          "
        >
          <span
            class="w-1.5 h-1.5 rounded-full shrink-0"
            :style="{ backgroundColor: agent.colorHex }"
          ></span>
          <span>{{ agent.label }}</span>
        </button>
      </div>
    </div>

    <!-- Quick Action Buttons -->
    <div class="flex flex-col gap-1.5 pt-1 w-full">
      <div class="grid grid-cols-3 gap-1.5 w-full">
        <button
          type="button"
          @click="emit('approve')"
          data-test="hitl-approve-btn"
          class="h-8.5 w-full bg-emerald-500/15 hover:bg-emerald-500/30 border border-emerald-500/60 text-emerald-400 font-mono text-xs font-bold rounded-lg transition-colors flex items-center justify-center gap-1.5 shadow-sm cursor-pointer"
          title="Aceptar dictamen y continuar"
        >
          <Check class="w-3.5 h-3.5 shrink-0" />
          <span>Aceptar</span>
        </button>
        <button
          type="button"
          @click="emit('consolidate')"
          data-test="hitl-consolidate-btn"
          class="h-8.5 w-full bg-purple-500/15 hover:bg-purple-500/30 border border-purple-500/60 text-purple-400 font-mono text-xs font-bold rounded-lg transition-colors flex items-center justify-center gap-1.5 shadow-sm cursor-pointer"
          title="Concluir el debate anticipadamente y consolidar dictamen final con Atenea"
        >
          <Sparkles class="w-3.5 h-3.5 shrink-0" />
          <span>Consolidar</span>
        </button>
        <button
          type="button"
          @click="emit('finish')"
          data-test="hitl-finish-btn"
          class="h-8.5 w-full bg-rose-500/15 hover:bg-rose-500/30 border border-rose-500/60 text-rose-400 font-mono text-xs font-bold rounded-lg transition-colors flex items-center justify-center gap-1.5 shadow-sm cursor-pointer"
          title="Parar y finalizar el debate inmediatamente sin consolidar"
        >
          <Square class="w-3.5 h-3.5 shrink-0" />
          <span>Finalizar</span>
        </button>
      </div>

      <div class="grid grid-cols-3 gap-1.5 w-full">
        <button
          type="button"
          @click="emit('refine')"
          data-test="hitl-refine-btn"
          class="h-8.5 w-full bg-neon-amber/15 hover:bg-neon-amber/30 border border-neon-amber/60 text-neon-amber font-mono text-xs font-bold rounded-lg transition-colors flex items-center justify-center gap-1.5 shadow-sm cursor-pointer"
          title="Refinar con nuevas instrucciones"
        >
          <Edit3 class="w-3.5 h-3.5 shrink-0" />
          <span>Refinar</span>
        </button>
        <button
          type="button"
          @click="emit('divert')"
          data-test="hitl-divert-btn"
          class="h-8.5 w-full bg-cyan-500/15 hover:bg-cyan-500/30 border border-cyan-500/60 text-cyan-400 font-mono text-xs font-bold rounded-lg transition-colors flex items-center justify-center gap-1.5 shadow-sm cursor-pointer"
          title="Desviar deliberación a los agentes seleccionados arriba"
        >
          <GitFork class="w-3.5 h-3.5 shrink-0" />
          <span>Desviar</span>
        </button>
        <button
          type="button"
          @click="emit('reject')"
          data-test="hitl-reject-btn"
          class="h-8.5 w-full bg-red-500/15 hover:bg-red-500/30 border border-red-500/60 text-red-400 font-mono text-xs font-bold rounded-lg transition-colors flex items-center justify-center gap-1.5 shadow-sm cursor-pointer"
          title="Rechazar propuesta y reiniciar deliberación"
        >
          <X class="w-3.5 h-3.5 shrink-0" />
          <span>Rechazar</span>
        </button>
      </div>
    </div>
  </div>
</template>

