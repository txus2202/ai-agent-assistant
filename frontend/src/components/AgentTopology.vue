<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { useDebateStore, type Agent } from '../stores/debate'
import AgentCard from './AgentCard.vue'

const store = useDebateStore()

const props = defineProps<{
  agents: Agent[]
}>()

const listContainer = ref<HTMLElement | null>(null)

const displayedAgents = computed(() => {
  return (props.agents || []).filter(a => a.role !== 'supervisor')
})

const isAgentActive = (agentRole: string, agentState: string) => {
  if (store.activeTtsRole) {
    const normTts = store.normalizeAgentRole ? store.normalizeAgentRole(store.activeTtsRole) : store.activeTtsRole
    const normAgent = store.normalizeAgentRole ? store.normalizeAgentRole(agentRole) : agentRole
    if (normTts === normAgent) return true
  }
  return agentState === 'ACTIVE'
}

// Watch for changes in displayedAgents or activeTtsRole to trigger scrollIntoView on the active one
watch(
  () => [displayedAgents.value, store.activeTtsRole],
  async () => {
    const activeIndex = displayedAgents.value.findIndex(a => isAgentActive(a.role, a.state))
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
    <div class="p-3 sm:p-4 border-b border-space-800 flex items-center justify-between gap-2">
      <h2 class="text-xs font-mono text-neon-cyan tracking-[0.15em] uppercase flex items-center shrink-0">
        <span class="inline-block w-2 h-2 bg-neon-cyan rounded-full mr-2 animate-pulse"></span>
        AGENTES
      </h2>
    </div>

    <!-- Scrollable Agent List -->
    <div 
      ref="listContainer"
      data-test="topology-scroll-container" 
      class="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-4"
    >
      <div v-if="displayedAgents.length === 0" data-test="empty-agents-message" class="text-xs text-slate-500 font-mono text-center py-8">
        No agents available
      </div>
      <AgentCard
        v-for="agent in displayedAgents"
        :key="agent.role"
        :role="agent.role"
        :roleName="agent.name"
        :description="agent.description"
        :colorHex="agent.color_hex"
        :state="isAgentActive(agent.role, agent.state) ? 'ACTIVE' : agent.state"
        :tokensConsumed="agent.tokens"
        :promptTokens="agent.promptTokens"
        :completionTokens="agent.completionTokens"
        :latencySeconds="agent.latency"
        :turnsCount="agent.turns"
        :usesRag="agent.uses_rag"
        :supportsHitl="agent.supports_hitl"
        :canIngestDocuments="agent.can_ingest_documents"
        :topologyRoles="agent.topology_roles"
      />
    </div>

    <!-- Orchestration Panel (Bottom Fixed) -->
    <div class="p-4 border-t border-space-800 bg-space-900">
      <slot name="orchestration"></slot>
    </div>
  </div>
</template>
