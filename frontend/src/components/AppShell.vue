<script setup lang="ts">
import { computed, ref } from 'vue'
import { useDebateStore } from '../stores/debate'
import ChatPanel from './ChatPanel.vue'
import ParticleOrb from './ParticleOrb.vue'
import AgentTopology from './AgentTopology.vue'
import AppHeader from './AppHeader.vue'

const store = useDebateStore()
const chatPanelRef = ref<InstanceType<typeof ChatPanel> | null>(null)

const DEFAULT_COLOR = '#00e5ff'

const activeAgentColor = computed(() => {
  if (store.activeTtsRole) {
    const ttsAgent = store.findAgent ? store.findAgent(store.activeTtsRole) : store.agents.find(a => a.role === store.activeTtsRole)
    if (ttsAgent?.color_hex) return ttsAgent.color_hex
    if (store.activeTtsRole === 'supervisor') return '#f59e0b'
    return DEFAULT_COLOR
  }
  
  const activeAgent = store.agents.find(a => a.state === 'ACTIVE')
  if (!activeAgent) return DEFAULT_COLOR
  
  return activeAgent.color_hex || DEFAULT_COLOR
})



</script>

<template>
  <div class="h-screen w-full bg-space-950 flex flex-col overflow-hidden text-slate-300 font-sans">
    
    <!-- Top Header -->
    <AppHeader />

    <!-- 3-Column Layout -->
    <div class="flex-1 flex flex-col md:flex-row overflow-hidden relative">
      <!-- Left Column: Chat Panel -->
      <div class="w-full md:w-1/3 lg:w-1/4 h-1/2 md:h-full z-10">
        <ChatPanel 
          ref="chatPanelRef"
          :messages="store.messages"
          :is-debating="store.isDebating"
        />
      </div>

      <!-- Middle Column: Particle Orb & Canvas -->
      <div class="w-full md:flex-1 h-1/2 md:h-full relative z-0 flex flex-col bg-[#04070d]">
      
      <ParticleOrb 
        :active-agent-color="activeAgentColor"
        :is-debating="store.isDebating || store.isTtsPlaying"
        @submit-draft="chatPanelRef?.onSubmit()"
        class="flex-1"
      />
    </div>

    <!-- Right Column: Agent Topology & Orchestration -->
    <div class="w-full md:w-1/3 lg:w-[400px] h-1/2 md:h-full z-10 bg-space-900/50 backdrop-blur-md flex flex-col">
      <AgentTopology class="flex-1" :agents="store.agents">
        <template #orchestration>
          <div class="flex flex-col space-y-2">
            <h3 class="text-[10px] font-mono text-slate-500 uppercase tracking-widest mb-1">
              Consejo Técnico
            </h3>
            <div class="p-3 bg-space-950/60 border border-space-800 rounded text-slate-400 font-mono text-xs flex items-center justify-between">
              <span class="flex items-center gap-2">
                <span class="w-1.5 h-1.5 rounded-full" :class="store.isDebating ? 'bg-neon-green animate-pulse' : 'bg-slate-500'"></span>
                <span>{{ store.isDebating ? 'Debate en curso' : 'Consejo en espera' }}</span>
              </span>
              <span v-if="store.isHitlRequired" class="text-neon-amber text-[10px] uppercase font-bold animate-pulse">
                HITL Activo
              </span>
            </div>
          </div>
        </template>
      </AgentTopology>
    </div>

    </div>
  </div>
</template>
