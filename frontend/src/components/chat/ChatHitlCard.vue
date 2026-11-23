<script setup lang="ts">
import { ref, watch } from 'vue'
import { Check, ChevronDown, Edit3, GitFork, RotateCcw, Sparkles, Square, X } from '@lucide/vue'
import { useTouchSwipe } from '../../utils/touchSwipe'

export interface HitlSelectableAgent {
  value: string
  label: string
  colorHex: string
}

const props = withDefaults(
  defineProps<{
    selectableAgents: HitlSelectableAgent[]
    selectedTargets: string[]
    hasErrorRecovery: boolean
    collapsible?: boolean
    initialCollapsed?: boolean | null
  }>(),
  {
    collapsible: true,
    initialCollapsed: null,
  },
)

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

const hitlCardRef = ref<HTMLElement | null>(null)
const isMobile = typeof window !== 'undefined' ? window.innerWidth < 768 : false
const isCollapsed = ref(props.initialCollapsed ?? isMobile)

watch(
  () => props.initialCollapsed,
  (val) => {
    if (typeof val === 'boolean') {
      isCollapsed.value = val
    }
  },
)

const toggleCollapse = () => {
  if (!props.collapsible) return
  isCollapsed.value = !isCollapsed.value
}

const expand = () => {
  if (!props.collapsible) return
  isCollapsed.value = false
}

const collapse = () => {
  if (!props.collapsible) return
  isCollapsed.value = true
}

useTouchSwipe(hitlCardRef, {
  ignoreInteractive: false,
  onSwipeUp: expand,
  onSwipeDown: collapse,
})

const isSelected = (role: string) => props.selectedTargets.includes(role)
</script>

<template>
  <div
    ref="hitlCardRef"
    data-test="hitl-chat-card"
    class="mb-3 p-2.5 sm:p-3.5 bg-[#080d1a] border border-neon-amber/60 rounded-xl shadow-[0_0_20px_rgba(245,158,11,0.15)] flex flex-col gap-2 transition-all duration-300 animate-fade-in"
  >
    <!-- Header Bar: Title, Toggle Chevron & Retry -->
    <div class="flex items-center justify-between gap-2">
      <div
        class="flex items-center gap-2 select-none min-w-0"
        :class="{ 'cursor-pointer': collapsible }"
        :role="collapsible ? 'button' : undefined"
        :tabindex="collapsible ? 0 : undefined"
        @click="toggleCollapse"
        @keydown.enter.space.prevent="toggleCollapse"
        title="Punto de control de decisión humana (HITL)"
      >
        <span class="w-2 h-2 rounded-full bg-neon-amber animate-pulse shrink-0"></span>
        <span class="text-xs font-mono font-bold text-neon-amber tracking-wider uppercase truncate">
          Punto de Control (HITL)
        </span>
        <span
          v-if="collapsible && isCollapsed"
          class="text-[9px] font-mono text-amber-300/70 border border-amber-500/30 rounded px-1.5 py-0.5 hidden sm:inline-block tracking-tight shrink-0"
        >
          PULSA PARA DESPLEGAR
        </span>
      </div>

      <div class="flex items-center gap-1.5 shrink-0">
        <!-- Collapse/Expand Toggle Button (matching SoundBar.vue style) -->
        <button
          v-if="collapsible"
          type="button"
          @click="toggleCollapse"
          data-test="hitl-collapse-toggle"
          class="p-1 sm:p-1.5 rounded-lg border border-space-700/80 bg-space-850 hover:bg-space-800 text-slate-400 hover:text-neon-amber hover:border-neon-amber/40 transition-colors flex items-center justify-center cursor-pointer"
          :title="isCollapsed ? 'Desplegar acciones HITL' : 'Ocultar acciones HITL'"
          :aria-label="isCollapsed ? 'Desplegar acciones HITL' : 'Ocultar acciones HITL'"
          :aria-expanded="!isCollapsed"
        >
          <ChevronDown
            class="w-3.5 h-3.5 transition-transform duration-300 ease-out"
            :class="isCollapsed ? 'rotate-180 text-neon-amber' : 'rotate-0 text-slate-400'"
          />
        </button>

        <!-- Retry Button -->
        <button
          type="button"
          @click="emit('retry')"
          data-test="hitl-retry-btn"
          class="p-1 sm:p-1.5 rounded-lg border transition-all flex items-center justify-center cursor-pointer group"
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
    </div>

    <!-- Collapsible Body with Smooth Transition -->
    <Transition
      enter-active-class="transition-all duration-300 ease-out overflow-hidden"
      enter-from-class="opacity-0 max-h-0"
      enter-to-class="opacity-100 max-h-[320px]"
      leave-active-class="transition-all duration-200 ease-in overflow-hidden"
      leave-from-class="opacity-100 max-h-[320px]"
      leave-to-class="opacity-0 max-h-0"
    >
      <div
        v-show="!collapsible || !isCollapsed"
        data-test="hitl-card-body"
        class="flex flex-col gap-2.5 pt-0.5"
      >
        <!-- Target Agents Chips Selector -->
        <div v-if="selectableAgents.length > 0" class="flex flex-col gap-1.5 pt-0.5">
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
        <div class="flex flex-col gap-1.5 pt-0.5 w-full">
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
    </Transition>
  </div>
</template>

