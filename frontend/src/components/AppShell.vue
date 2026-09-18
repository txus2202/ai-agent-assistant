<script setup lang="ts">
import { computed } from 'vue'
import { useDebateStore } from '../stores/debate'
import ChatPanel from './ChatPanel.vue'
import ParticleOrb from './ParticleOrb.vue'
import AgentTopology from './AgentTopology.vue'
import HITLActionButton from './HITLActionButton.vue'
import { AGENT_THEME, DEFAULT_AGENT_THEME } from '../config/agentTheme'

const store = useDebateStore()

const activeAgentColor = computed(() => {
  const activeAgent = store.agents.find(a => a.state === 'ACTIVE')
  if (!activeAgent) return DEFAULT_AGENT_THEME.hex
  
  return AGENT_THEME[activeAgent.role]?.hex || DEFAULT_AGENT_THEME.hex
})

const handleUserSubmit = (request: string) => {
  store.startDebate(request)
}

const handleHitlAction = (decision: 'approve' | 'refine' | 'reject') => {
  store.submitHitlDecision(decision)
}
</script>

<template>
  <div class="h-screen w-full bg-space-950 flex flex-col md:flex-row overflow-hidden text-slate-300 font-sans">
    
    <!-- Left Column: Chat Panel -->
    <div class="w-full md:w-1/3 lg:w-1/4 h-1/2 md:h-full z-10">
      <ChatPanel 
        :messages="store.messages"
        :is-debating="store.isDebating"
        @submit="handleUserSubmit"
      />
    </div>

    <!-- Middle Column: Particle Orb & Canvas -->
    <div class="w-full md:flex-1 h-1/2 md:h-full relative z-0">
      <div class="absolute top-6 left-6 z-10 pointer-events-none">
        <h1 class="text-3xl font-mono font-bold tracking-widest text-white mix-blend-overlay opacity-50">
          A.T.E.N.E.A
        </h1>
        <p class="text-xs font-mono text-neon-cyan tracking-[0.3em] uppercase mt-2">
          Autonomous Agentic Architecture
        </p>
      </div>
      
      <ParticleOrb 
        :active-agent-color="activeAgentColor"
        :is-debating="store.isDebating"
      />
    </div>

    <!-- Right Column: Agent Topology & Orchestration -->
    <div class="w-full md:w-1/3 lg:w-[400px] h-1/2 md:h-full z-10 bg-space-900/50 backdrop-blur-md">
      <AgentTopology :agents="store.agents">
        <template #orchestration>
          <div class="flex flex-col space-y-3">
            <h3 class="text-[10px] font-mono text-slate-500 uppercase tracking-widest mb-1">
              Manual Override (HITL)
            </h3>
            
            <div class="grid grid-cols-2 gap-2" v-if="store.isHitlRequired">
              <HITLActionButton 
                decision="approve"
                @action="handleHitlAction"
              />
              <HITLActionButton 
                decision="refine"
                @action="handleHitlAction"
              />
            </div>
            
            <div v-else class="text-center p-4 border border-space-800 border-dashed rounded text-space-700 font-mono text-xs uppercase">
              No checkpoints requiring attention
            </div>
          </div>
        </template>
      </AgentTopology>
    </div>

  </div>
</template>
