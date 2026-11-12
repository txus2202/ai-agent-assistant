<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { Bot, Activity } from '@lucide/vue'
import { useDebateStore, type Agent } from '../stores/debate'
import AgentCard from './AgentCard.vue'
import ObservabilityPanel from './ObservabilityPanel.vue'

const store = useDebateStore()

const props = withDefaults(defineProps<{
  agents: Agent[]
  initialTab?: 'agents' | 'observability'
}>(), {
  initialTab: 'agents'
})

const activeTab = ref<'agents' | 'observability'>(props.initialTab)
watch(() => props.initialTab, (val) => {
  if (val) activeTab.value = val
})

const listContainer = ref<HTMLElement | null>(null)

const setActiveTab = (tab: 'agents' | 'observability') => {
  activeTab.value = tab
}

defineExpose({
  setActiveTab
})

const displayedAgents = computed(() => {
  const all = [...(props.agents || [])]
  return all.sort((a, b) => {
    if (a.role === 'supervisor') return -1
    if (b.role === 'supervisor') return 1
    return 0
  })
})

const isAgentActive = (agentRole: string, agentState: string) => {
  if (agentState === 'ERROR') {
    return false
  }
  const normAgent = (store.normalizeAgentRole ? store.normalizeAgentRole(agentRole) : agentRole).toLowerCase()
  const isSupervisor = normAgent === 'supervisor' || normAgent === 'atenea'

  // If it's Atenea and debate or TTS is running, she is actively coordinating the council and her card stays illuminated
  if (isSupervisor && (store.isDebating || store.isTtsPlaying || Boolean(store.readingAgentRoles && store.readingAgentRoles.length > 0))) {
    return true
  }

  if (typeof store.isAgentReading === 'function' && store.isAgentReading(agentRole)) {
    return true
  }
  if (store.activeTtsRole) {
    const normTts = (store.normalizeAgentRole ? store.normalizeAgentRole(store.activeTtsRole) : store.activeTtsRole).toLowerCase()
    if (normTts === normAgent) return true
    if (isSupervisor && (normTts === 'supervisor' || normTts === 'atenea')) return true
  }
  if (isSupervisor && !store.isDebating && !store.isTtsPlaying && !(store.readingAgentRoles && store.readingAgentRoles.length > 0)) {
    return false
  }
  return agentState === 'ACTIVE'
}

// Watch for changes in displayedAgents, store.isDebating, activeTtsRole or readingAgentRoles to trigger scrollIntoView on the active one
watch(
  () => [displayedAgents.value, store.isDebating, store.activeTtsRole, store.readingAgentRoles],
  async () => {
    // Prioritize scrolling to an active delegated specialist if one is working; otherwise scroll to active supervisor
    const delegatedActiveIndex = displayedAgents.value.findIndex(a => a.role !== 'supervisor' && isAgentActive(a.role, a.state))
    const activeIndex = delegatedActiveIndex !== -1 ? delegatedActiveIndex : displayedAgents.value.findIndex(a => isAgentActive(a.role, a.state))
    if (activeIndex !== -1) {
      await nextTick()
      const activeEl = listContainer.value?.children[activeIndex] as HTMLElement | undefined
      activeEl?.scrollIntoView?.({ behavior: 'smooth', block: 'center' })
    }
  },
  { deep: true }
)
</script>

<template>
  <div class="h-full flex flex-col border-l border-space-800 bg-space-900/50 backdrop-blur-sm min-h-0">
    <!-- Header: Tabs for Agentes & Observabilidad (Desktop/Tablet only, redundant on mobile with bottom nav) -->
    <div class="hidden md:flex py-3.5 px-4 border-b border-space-800 items-center justify-between shrink-0">
      <div class="flex items-center gap-2 w-full">
        <button 
          type="button"
          @click="activeTab = 'agents'"
          data-test="tab-agents"
          :class="activeTab === 'agents' 
            ? 'border-cyan-400 bg-space-800 text-neon-cyan shadow-[0_0_12px_rgba(0,229,255,0.18)] tab-active-btn' 
            : 'border-cyan-800/40 bg-space-850 hover:bg-space-800 hover:text-cyan-200 hover:border-cyan-500/50 text-slate-400'"
          class="flex-1 h-[34px] min-h-[34px] flex items-center justify-center px-2.5 font-mono text-[10px] tracking-wider uppercase transition-all rounded-lg border cursor-pointer select-none group"
        >
          <div class="flex items-center space-x-1.5 min-w-0">
            <Bot class="w-3.5 h-3.5 shrink-0" />
            <span>Agentes</span>
          </div>
        </button>

        <button 
          type="button"
          @click="activeTab = 'observability'"
          data-test="tab-observability"
          :class="activeTab === 'observability' 
            ? 'border-cyan-400 bg-space-800 text-neon-cyan shadow-[0_0_12px_rgba(0,229,255,0.18)] tab-active-btn' 
            : 'border-cyan-800/40 bg-space-850 hover:bg-space-800 hover:text-cyan-200 hover:border-cyan-500/50 text-slate-400'"
          class="flex-1 h-[34px] min-h-[34px] flex items-center justify-center px-2.5 font-mono text-[10px] tracking-wider uppercase transition-all rounded-lg border cursor-pointer select-none group"
        >
          <div class="flex items-center space-x-1.5 min-w-0">
            <Activity class="w-3.5 h-3.5 shrink-0" />
            <span>Observabilidad</span>
          </div>
        </button>
      </div>
    </div>

    <!-- Observability View -->
    <ObservabilityPanel v-if="activeTab === 'observability'" class="flex-1 min-h-0 overflow-y-auto" />

    <!-- Agents View (List + Orchestration Footer) -->
    <template v-else>
      <!-- Scrollable Agent List -->
      <div 
        ref="listContainer"
        data-test="topology-scroll-container" 
        class="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-4 min-h-0"
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

      <!-- Orchestration Panel (Bottom Fixed, Height matches ChatPanel input container on desktop) -->
      <div class="p-4 border-t border-space-800 bg-space-900 shrink-0 md:h-[162px] flex flex-col justify-center">
        <slot name="orchestration"></slot>
      </div>
    </template>
  </div>
</template>
