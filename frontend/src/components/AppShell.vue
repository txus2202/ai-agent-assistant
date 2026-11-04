<script setup lang="ts">
import { computed, ref, nextTick } from 'vue'
import { useDebateStore } from '../stores/debate'
import ChatPanel from './ChatPanel.vue'
import ParticleOrb from './ParticleOrb.vue'
import AgentTopology from './AgentTopology.vue'
import AppHeader from './AppHeader.vue'
import ObservabilityPanel from './ObservabilityPanel.vue'

type MobileTab = 'chat' | 'voice' | 'agents' | 'telemetry'
type TabletRightTab = 'orb' | 'agents' | 'telemetry'

const store = useDebateStore()
const chatPanelRef = ref<InstanceType<typeof ChatPanel> | null>(null)
const particleOrbRef = ref<InstanceType<typeof ParticleOrb> | null>(null)
const agentTopologyRef = ref<InstanceType<typeof AgentTopology> | null>(null)

const mobileTab = ref<MobileTab>('chat')
const tabletRightTab = ref<TabletRightTab>('orb')

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

const activeAgentStatusTitle = computed(() => {
  if (store.isRecording) {
    return 'Escuchando orden por voz...'
  }
  if (store.activeTtsRole) {
    const ttsAgent = store.findAgent ? store.findAgent(store.activeTtsRole) : store.agents.find(a => a.role === store.activeTtsRole)
    const speakerName = ttsAgent?.name || (store.activeTtsRole === 'supervisor' ? 'Atenea' : store.activeTtsRole)
    return `${speakerName} hablando...`
  }
  const activeAgent = store.agents.find(a => a.state === 'ACTIVE')
  if (activeAgent) {
    return `${activeAgent.name} sintetizando...`
  }
  if (store.isDebating) {
    return 'Debate adaptativo en curso...'
  }
  return 'Atenea en línea y a la espera'
})

const selectMobileTab = async (tab: MobileTab) => {
  mobileTab.value = tab
  if (tab === 'telemetry') {
    chatPanelRef.value?.setActiveTab?.('observability')
    agentTopologyRef.value?.setActiveTab?.('observability')
  } else if (tab === 'chat') {
    chatPanelRef.value?.setActiveTab?.('chat')
  } else if (tab === 'agents') {
    agentTopologyRef.value?.setActiveTab?.('agents')
  } else if (tab === 'voice') {
    await nextTick()
    particleOrbRef.value?.resizeCanvas?.()
  }
}

const selectTabletRightTab = async (tab: TabletRightTab) => {
  tabletRightTab.value = tab
  if (tab === 'orb') {
    await nextTick()
    particleOrbRef.value?.resizeCanvas?.()
  }
}

const handleToggleMic = () => {
  particleOrbRef.value?.toggleRecording?.()
}
</script>

<template>
  <div class="h-screen w-full bg-space-950 flex flex-col overflow-hidden text-slate-900 dark:text-slate-300 font-sans">
    
    <!-- Top Header -->
    <AppHeader />

    <!-- Responsive Workspace: 1-Col Mobile / 2-Col Tablet Split / 3-Col Desktop -->
    <div class="flex-1 flex flex-col md:flex-row overflow-hidden relative min-h-0">
      
      <!-- Left Column: Chat Panel (+ Mobile Contextual Mini-Orb Bar) -->
      <div
        data-test="shell-left-column"
        :class="mobileTab === 'chat' ? 'flex' : 'hidden'"
        class="w-full md:flex md:w-[58%] lg:w-[380px] xl:w-[400px] lg:shrink-0 flex-1 md:flex-none md:h-full z-10 flex-col overflow-hidden min-h-0"
      >
        <!-- Mobile Contextual Mini-Orb Status Bar (Visible on mobile in Chat view) -->
        <button
          v-if="mobileTab === 'chat'"
          type="button"
          data-test="mobile-mini-orb-bar"
          @click="selectMobileTab('voice')"
          class="md:hidden w-full px-3.5 py-2 bg-[#09101d]/95 border-b border-space-800 flex items-center justify-between text-left transition-colors hover:bg-space-900 shrink-0"
        >
          <div class="flex items-center gap-2.5 min-w-0">
            <span
              class="w-5 h-5 rounded-full shrink-0 transition-all duration-500"
              :class="(store.isDebating || store.isTtsPlaying || store.isRecording) ? 'animate-pulse scale-110' : ''"
              :style="{
                backgroundColor: activeAgentColor,
                boxShadow: `0 0 12px ${activeAgentColor}`
              }"
            ></span>
            <div class="min-w-0">
              <div class="text-[11px] font-bold text-slate-200 truncate">
                {{ activeAgentStatusTitle }}
              </div>
              <div class="text-[9px] text-cyan-400/70 font-mono truncate">
                {{ store.isDebating ? 'Debate adaptativo activo • Pulsa para Orbe 3D' : 'Pulsa para abrir Orbe de Voz 3D' }}
              </div>
            </div>
          </div>
          <div class="flex items-center gap-1.5 shrink-0 ml-2">
            <span
              v-if="store.isHitlRequired"
              class="text-[9px] px-2 py-0.5 rounded bg-amber-950 text-neon-amber border border-neon-amber/50 font-mono font-bold uppercase animate-pulse"
            >
              HITL
            </span>
            <span class="text-[10px] font-mono text-cyan-400/80 bg-cyan-950/50 border border-cyan-500/30 px-2 py-0.5 rounded">
              3D &gt;
            </span>
          </div>
        </button>

        <ChatPanel 
          ref="chatPanelRef"
          class="flex-1 min-h-0"
          :messages="store.messages"
          :is-debating="store.isDebating"
          @toggle-mic="handleToggleMic"
        />
      </div>

      <!-- Center & Right Workspace Group (Tablet 42% Right Column / Desktop Center + Right Columns) -->
      <div
        data-test="shell-secondary-group"
        :class="(mobileTab === 'voice' || mobileTab === 'agents' || mobileTab === 'telemetry') ? 'flex' : 'hidden'"
        class="w-full md:flex md:w-[42%] lg:w-auto flex-1 flex-col overflow-hidden min-w-0 min-h-0 md:h-full"
      >
        <!-- Tablet Segmented Control Header (768px - 1023px: md to lg) -->
        <div
          data-test="tablet-segmented-control"
          class="hidden md:flex lg:hidden items-center justify-between gap-1.5 p-2 bg-[#080d17] border-b border-space-800 shrink-0"
        >
          <button
            type="button"
            data-test="tablet-tab-orb"
            @click="selectTabletRightTab('orb')"
            :class="tabletRightTab === 'orb'
              ? 'bg-neon-cyan text-space-950 font-bold shadow-[0_0_10px_rgba(0,229,255,0.3)]'
              : 'text-slate-400 hover:text-cyan-300 hover:bg-space-900'"
            class="flex-1 py-1.5 px-2 min-h-[36px] rounded text-[11px] font-mono uppercase tracking-wider transition-all flex items-center justify-center gap-1.5 cursor-pointer"
          >
            <span class="w-2 h-2 rounded-full" :style="{ backgroundColor: tabletRightTab === 'orb' ? '#060a11' : activeAgentColor }"></span>
            <span>Orbe 3D</span>
          </button>
          <button
            type="button"
            data-test="tablet-tab-agents"
            @click="selectTabletRightTab('agents')"
            :class="tabletRightTab === 'agents'
              ? 'bg-neon-cyan text-space-950 font-bold shadow-[0_0_10px_rgba(0,229,255,0.3)]'
              : 'text-slate-400 hover:text-cyan-300 hover:bg-space-900'"
            class="flex-1 py-1.5 px-2 min-h-[36px] rounded text-[11px] font-mono uppercase tracking-wider transition-all flex items-center justify-center gap-1.5 cursor-pointer"
          >
            <span>Agentes</span>
            <span v-if="store.isDebating" class="w-1.5 h-1.5 rounded-full bg-neon-green animate-ping"></span>
          </button>
          <button
            type="button"
            data-test="tablet-tab-telemetry"
            @click="selectTabletRightTab('telemetry')"
            :class="tabletRightTab === 'telemetry'
              ? 'bg-neon-cyan text-space-950 font-bold shadow-[0_0_10px_rgba(0,229,255,0.3)]'
              : 'text-slate-400 hover:text-cyan-300 hover:bg-space-900'"
            class="flex-1 py-1.5 px-2 min-h-[36px] rounded text-[11px] font-mono uppercase tracking-wider transition-all flex items-center justify-center gap-1.5 cursor-pointer"
          >
            <span>Telemetría</span>
          </button>
        </div>

        <!-- Inner Columns Container -->
        <div class="flex-1 flex flex-col lg:flex-row overflow-hidden relative min-h-0">
          
          <!-- Middle Column: Particle Orb & Canvas -->
          <div
            data-test="shell-orb-column"
            :class="[
              mobileTab === 'voice' ? 'flex' : 'hidden',
              tabletRightTab === 'orb' ? 'md:flex' : 'md:hidden',
              'lg:flex'
            ]"
            class="w-full flex-1 h-full relative z-0 flex-col bg-[#04070d] min-h-0"
          >
            <ParticleOrb 
              ref="particleOrbRef"
              :active-agent-color="activeAgentColor"
              :is-debating="store.isDebating || store.isTtsPlaying"
              @submit-draft="chatPanelRef?.onSubmit()"
              class="flex-1"
            />
          </div>

          <!-- Right Column: Agent Topology & Observability -->
          <div
            data-test="shell-agents-column"
            :class="[
              (mobileTab === 'agents' || mobileTab === 'telemetry') ? 'flex' : 'hidden',
              tabletRightTab === 'agents' ? 'md:flex' : 'md:hidden',
              'lg:flex'
            ]"
            class="w-full lg:w-[380px] xl:w-[400px] lg:shrink-0 flex-1 lg:flex-none h-full z-10 bg-space-900/50 backdrop-blur-md flex-col min-h-0"
          >
            <AgentTopology 
              ref="agentTopologyRef"
              class="flex-1" 
              :agents="store.agents"
              :initial-tab="mobileTab === 'telemetry' ? 'observability' : 'agents'"
            >
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

          <!-- Tablet Side-by-Side Telemetry Column (visible on Tablet when tabletRightTab === 'telemetry') -->
          <div
            v-if="tabletRightTab === 'telemetry'"
            data-test="shell-tablet-telemetry"
            class="hidden md:flex lg:hidden w-full flex-1 h-full flex-col overflow-hidden bg-[#060a11] min-h-0"
          >
            <ObservabilityPanel class="flex-1" />
          </div>

        </div>
      </div>

    </div>

    <!-- Mobile Bottom Navigation Bar (< 768px) -->
    <nav
      data-test="mobile-bottom-nav"
      aria-label="Navegación principal móvil"
      class="md:hidden border-t border-cyan-900/40 bg-[#080e1a]/95 backdrop-blur-md px-2 py-1 pb-[max(0.25rem,env(safe-area-inset-bottom))] flex items-center justify-around z-30 shrink-0"
    >
      <button
        type="button"
        data-test="mobile-nav-chat"
        @click="selectMobileTab('chat')"
        :class="mobileTab === 'chat' ? 'text-neon-cyan' : 'text-slate-500 hover:text-slate-300'"
        class="relative flex-1 min-h-[48px] flex flex-col items-center justify-center gap-1 transition-colors"
      >
        <span
          v-if="mobileTab === 'chat'"
          class="absolute top-0 w-8 h-0.5 bg-neon-cyan shadow-[0_0_8px_#00e5ff] rounded-full"
        ></span>
        <span
          v-if="store.isHitlRequired"
          class="absolute top-1.5 right-1/4 w-2 h-2 rounded-full bg-neon-amber animate-ping"
        ></span>
        <svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
        <span class="text-[10px] font-mono font-bold tracking-tight">Chat</span>
      </button>

      <button
        type="button"
        data-test="mobile-nav-voice"
        @click="selectMobileTab('voice')"
        :class="mobileTab === 'voice' ? 'text-neon-cyan' : 'text-slate-500 hover:text-slate-300'"
        class="relative flex-1 min-h-[48px] flex flex-col items-center justify-center gap-1 transition-colors"
      >
        <span
          v-if="mobileTab === 'voice'"
          class="absolute top-0 w-8 h-0.5 bg-neon-cyan shadow-[0_0_8px_#00e5ff] rounded-full"
        ></span>
        <span
          v-if="store.isRecording || store.isTtsPlaying"
          class="absolute top-1.5 right-1/4 w-2 h-2 rounded-full animate-pulse"
          :style="{ backgroundColor: activeAgentColor }"
        ></span>
        <svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"></path><path d="M2 12h20"></path></svg>
        <span class="text-[10px] font-mono font-bold tracking-tight">Voz 3D</span>
      </button>

      <button
        type="button"
        data-test="mobile-nav-agents"
        @click="selectMobileTab('agents')"
        :class="mobileTab === 'agents' ? 'text-neon-cyan' : 'text-slate-500 hover:text-slate-300'"
        class="relative flex-1 min-h-[48px] flex flex-col items-center justify-center gap-1 transition-colors"
      >
        <span
          v-if="mobileTab === 'agents'"
          class="absolute top-0 w-8 h-0.5 bg-neon-cyan shadow-[0_0_8px_#00e5ff] rounded-full"
        ></span>
        <span
          v-if="store.isDebating"
          class="absolute top-1.5 right-1/4 w-2 h-2 rounded-full bg-neon-green animate-pulse"
        ></span>
        <svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M22 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>
        <span class="text-[10px] font-mono font-bold tracking-tight">Agentes</span>
      </button>

      <button
        type="button"
        data-test="mobile-nav-telemetry"
        @click="selectMobileTab('telemetry')"
        :class="mobileTab === 'telemetry' ? 'text-neon-cyan' : 'text-slate-500 hover:text-slate-300'"
        class="relative flex-1 min-h-[48px] flex flex-col items-center justify-center gap-1 transition-colors"
      >
        <span
          v-if="mobileTab === 'telemetry'"
          class="absolute top-0 w-8 h-0.5 bg-neon-cyan shadow-[0_0_8px_#00e5ff] rounded-full"
        ></span>
        <svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg>
        <span class="text-[10px] font-mono font-bold tracking-tight">Telemetría</span>
      </button>
    </nav>

  </div>
</template>
