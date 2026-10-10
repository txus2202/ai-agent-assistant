<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { useDebateStore } from '../stores/debate'
import AgentCard from './AgentCard.vue'
import { AGENT_THEME, DEFAULT_AGENT_THEME } from '../config/agentTheme'

const store = useDebateStore()

const props = defineProps<{
  agents: Array<{
    role: string
    name?: string
    state: 'STANDBY' | 'ACTIVE' | 'COMPLETED'
  }>
}>()

const listContainer = ref<HTMLElement | null>(null)

const getTheme = (role: string) => {
  return AGENT_THEME[role] || DEFAULT_AGENT_THEME
}

// Watch for changes in agents or activeTtsRole to trigger scrollIntoView on the active one
watch(
  () => [props.agents, store.activeTtsRole],
  async () => {
    const activeIndex = props.agents.findIndex(a => a.state === 'ACTIVE' || store.activeTtsRole === a.role)
    if (activeIndex !== -1) {
      await nextTick()
      const activeEl = listContainer.value?.children[activeIndex] as HTMLElement
      if (activeEl && activeEl.scrollIntoView) {
        activeEl.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    }
  },
  { deep: true }
)
</script>

<template>
  <div class="h-full flex flex-col border-l border-space-800 bg-space-900/50 backdrop-blur-sm">
    <!-- Header -->
    <div class="p-4 border-b border-space-800">
      <h2 class="text-xs font-mono text-neon-cyan tracking-[0.2em] uppercase">
        <span class="inline-block w-2 h-2 bg-neon-cyan rounded-full mr-2 animate-pulse"></span>
        Agent Topology
      </h2>
    </div>

    <!-- Scrollable Agent List -->
    <div 
      ref="listContainer"
      data-test="topology-scroll-container" 
      class="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-4"
    >
      <AgentCard
        v-for="agent in agents"
        :key="agent.role"
        :role="agent.role"
        :roleName="agent.name"
        :state="store.activeTtsRole === agent.role ? 'ACTIVE' : agent.state"
        :colorClass="getTheme(agent.role).colorClass"
        :glowClass="getTheme(agent.role).glowClass"
      />
    </div>

    <!-- Orchestration Panel (Bottom Fixed) -->
    <div class="p-4 border-t border-space-800 bg-space-900">
      <slot name="orchestration"></slot>
    </div>
  </div>
</template>
