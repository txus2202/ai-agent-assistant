<script setup lang="ts">
import { computed, ref } from 'vue'
import { useDebateStore } from '../stores/debate'
import ChatPanel from './ChatPanel.vue'
import ParticleOrb from './ParticleOrb.vue'
import AgentTopology from './AgentTopology.vue'
import HITLActionButton from './HITLActionButton.vue'
import EventStream from './EventStream.vue'
import { AGENT_THEME, DEFAULT_AGENT_THEME } from '../config/agentTheme'
import { History } from 'lucide-vue-next'
import { useRouter } from 'vue-router'

const store = useDebateStore()
const router = useRouter()

const activeAgentColor = computed(() => {
  const activeAgent = store.agents.find(a => a.state === 'ACTIVE')
  if (!activeAgent) return DEFAULT_AGENT_THEME.hex
  
  return AGENT_THEME[activeAgent.role]?.hex || DEFAULT_AGENT_THEME.hex
})

const handleUserSubmit = (request: string) => {
  store.startDebate(request)
}

const isRefining = ref(false)
const feedbackText = ref('')

const handleHitlAction = (decision: 'approve' | 'refine' | 'reject') => {
  if (decision === 'refine' && !isRefining.value) {
    // Reveal the textarea instead of submitting immediately
    isRefining.value = true
    return
  }
  
  store.submitHitlDecision(decision, feedbackText.value)
  isRefining.value = false
  feedbackText.value = ''
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

      <!-- Header actions -->
      <div class="absolute top-6 right-6 z-10">
        <button 
          @click="router.push('/history')"
          class="flex items-center space-x-2 px-3 py-2 bg-space-800/80 hover:bg-space-700 border border-space-600 rounded text-space-300 hover:text-neon-cyan transition-colors backdrop-blur font-mono text-xs"
        >
          <History class="w-4 h-4" />
          <span>HISTORY</span>
        </button>
      </div>
      
      <ParticleOrb 
        :active-agent-color="activeAgentColor"
        :is-debating="store.isDebating"
      />
    </div>

    <!-- Right Column: Agent Topology & Orchestration -->
    <div class="w-full md:w-1/3 lg:w-[400px] h-1/2 md:h-full z-10 bg-space-900/50 backdrop-blur-md flex flex-col">
      <AgentTopology class="flex-1" :agents="store.agents">
        <template #orchestration>
          <div class="flex flex-col space-y-3">
            <h3 class="text-[10px] font-mono text-slate-500 uppercase tracking-widest mb-1">
              Manual Override (HITL)
            </h3>
            
            <div v-if="store.isHitlRequired" class="flex flex-col space-y-2">
              <div v-if="!isRefining" class="grid grid-cols-2 gap-2">
                <HITLActionButton 
                  decision="approve"
                  @action="handleHitlAction"
                />
                <HITLActionButton 
                  decision="refine"
                  @action="handleHitlAction"
                />
              </div>
              
              <!-- Inline Refine Textarea -->
              <div v-else class="flex flex-col space-y-2 animate-fade-in">
                <textarea 
                  v-model="feedbackText"
                  class="w-full h-24 bg-space-950 border border-neon-amber/50 rounded p-2 text-sm font-mono text-slate-300 focus:outline-none focus:border-neon-amber focus:ring-1 focus:ring-neon-amber/50 resize-none custom-scrollbar"
                  placeholder="Provide your feedback to the agent..."
                ></textarea>
                <div class="flex justify-end space-x-2">
                  <button 
                    @click="isRefining = false"
                    class="px-3 py-1 text-xs font-mono text-slate-400 hover:text-slate-200 transition-colors"
                  >
                    CANCEL
                  </button>
                  <button 
                    @click="handleHitlAction('refine')"
                    :disabled="!feedbackText.trim()"
                    class="px-4 py-1 text-xs font-mono border border-neon-amber text-neon-amber rounded hover:bg-neon-amber/10 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    SEND FEEDBACK
                  </button>
                </div>
              </div>
            </div>
            
            <div v-else class="text-center p-4 border border-space-800 border-dashed rounded text-space-700 font-mono text-xs uppercase">
              No checkpoints requiring attention
            </div>
          </div>
        </template>
      </AgentTopology>

      <!-- NEW OBSERVABILITY PANEL -->
      <div class="h-64 border-t border-space-800 bg-space-950 flex flex-col">
        <EventStream :events="store.rawEvents" />
      </div>
    </div>

  </div>
</template>
