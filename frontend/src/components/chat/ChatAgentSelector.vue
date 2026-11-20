<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Check, ChevronDown } from '@lucide/vue'
import type { SelectableAgentOption } from './types'

const props = defineProps<{
  agents: SelectableAgentOption[]
  selectedAgents: string[]
  disabled: boolean
}>()

const emit = defineEmits<{
  (e: 'update:selectedAgents', next: string[]): void
}>()

const isOpen = ref(false)
const dropdownRef = ref<HTMLElement | null>(null)

const selectedLabel = computed(() => {
  const count = props.selectedAgents.length
  if (count === 0) return 'Seleccionar agente'
  if (count === 1) {
    const role = props.selectedAgents[0]
    return props.agents.find((a) => a.value === role)?.label || 'Atenea'
  }
  if (count === props.agents.length) {
    return `Todos los agentes (${count})`
  }
  if (count === 2) {
    const l1 = props.agents.find((a) => a.value === props.selectedAgents[0])?.label || ''
    const l2 = props.agents.find((a) => a.value === props.selectedAgents[1])?.label || ''
    return `${l1}, ${l2}`
  }
  return `${count} agentes seleccionados`
})

const toggleDropdown = () => {
  if (props.disabled) return
  isOpen.value = !isOpen.value
}

const toggleAgent = (role: string) => {
  const current = [...props.selectedAgents]
  const index = current.indexOf(role)
  if (index >= 0) {
    current.splice(index, 1)
    emit('update:selectedAgents', current.length > 0 ? current : ['supervisor'])
  } else if (current.length === 1 && current[0] === 'supervisor' && role !== 'supervisor') {
    emit('update:selectedAgents', [role])
  } else {
    emit('update:selectedAgents', [...current, role])
  }
}

const selectAllAgents = () => {
  if (props.selectedAgents.length === props.agents.length) {
    emit('update:selectedAgents', ['supervisor'])
  } else {
    emit(
      'update:selectedAgents',
      props.agents.map((a) => a.value),
    )
  }
}

const handleClickOutside = (event: MouseEvent) => {
  if (!dropdownRef.value || !isOpen.value) return
  const path = event.composedPath()
  if (!path.includes(dropdownRef.value)) {
    isOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<template>
  <div class="relative" ref="dropdownRef">
    <button
      type="button"
      @click="toggleDropdown"
      :disabled="disabled"
      data-test="agent-dropdown-btn"
      class="flex items-center justify-between min-w-[140px] max-w-[210px] min-h-[36px] md:min-h-0 bg-[#030509] border border-cyan-900/50 hover:border-neon-cyan/80 rounded px-3 py-1.5 text-[11px] font-mono text-cyan-50 shadow-[0_0_10px_-2px_rgba(0,229,255,0.1)] transition-all disabled:opacity-50"
    >
      <span class="truncate">{{ selectedLabel }}</span>
      <ChevronDown
        class="w-3 h-3 text-neon-cyan ml-2 shrink-0 transition-transform"
        :class="{ 'rotate-180': isOpen }"
      />
    </button>

    <div
      v-if="isOpen"
      class="absolute bottom-full left-0 mb-2 w-56 bg-space-950 border border-neon-cyan/50 rounded shadow-[0_0_15px_rgba(0,229,255,0.15)] overflow-hidden z-50 font-mono text-xs"
    >
      <div
        class="px-3 py-1.5 bg-space-900 text-neon-cyan/70 text-[9px] uppercase tracking-wider border-b border-neon-cyan/30 flex items-center justify-between"
      >
        <span>Agentes ({{ selectedAgents.length }})</span>
        <button
          type="button"
          @click.stop="selectAllAgents"
          class="text-[9px] text-neon-cyan hover:underline uppercase tracking-wider cursor-pointer"
        >
          {{ selectedAgents.length === agents.length ? 'Solo Atenea' : 'Todos' }}
        </button>
      </div>
      <div class="max-h-[220px] overflow-y-auto custom-scrollbar">
        <button
          v-for="agent in agents"
          :key="agent.value"
          type="button"
          @click.stop="toggleAgent(agent.value)"
          data-test="agent-option"
          :data-selected="selectedAgents.includes(agent.value)"
          class="w-full text-left px-3 py-2 transition-colors flex items-center justify-between cursor-pointer"
          :class="
            selectedAgents.includes(agent.value)
              ? 'bg-neon-cyan/10 text-neon-cyan'
              : 'text-slate-300 hover:bg-space-800 hover:text-cyan-200'
          "
        >
          <span class="flex items-center space-x-2 min-w-0">
            <span
              class="w-3.5 h-3.5 rounded-sm border flex items-center justify-center shrink-0 transition-colors"
              :class="
                selectedAgents.includes(agent.value)
                  ? 'border-neon-cyan bg-neon-cyan/20 text-neon-cyan'
                  : 'border-slate-700 bg-space-900'
              "
            >
              <Check v-if="selectedAgents.includes(agent.value)" class="w-2.5 h-2.5 stroke-[3]" />
            </span>
            <span
              class="w-1.5 h-1.5 rounded-full shrink-0"
              :style="agent.colorHex ? { backgroundColor: agent.colorHex } : {}"
            ></span>
            <span class="font-bold text-[10px] md:text-[11px] truncate">{{ agent.label }}</span>
          </span>
          <span
            v-if="selectedAgents.includes(agent.value)"
            class="w-1.5 h-1.5 rounded-full bg-neon-cyan glow-cyan shrink-0 ml-1"
          ></span>
        </button>
      </div>
    </div>
  </div>
</template>

