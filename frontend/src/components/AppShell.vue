<script setup lang="ts">
import { computed, ref, nextTick, onMounted, onUnmounted } from 'vue'
import { useDebateStore } from '../stores/debate'
import ChatPanel from './ChatPanel.vue'
import ParticleOrb from './ParticleOrb.vue'
import AgentTopology from './AgentTopology.vue'
import AppHeader from './AppHeader.vue'
import SoundBar from './SoundBar.vue'

type MobileTab = 'chat' | 'voice' | 'agents' | 'telemetry'

const store = useDebateStore()
const chatPanelRef = ref<InstanceType<typeof ChatPanel> | null>(null)
const particleOrbRef = ref<InstanceType<typeof ParticleOrb> | null>(null)
const agentTopologyRef = ref<InstanceType<typeof AgentTopology> | null>(null)
const mobileSoundBarRef = ref<InstanceType<typeof SoundBar> | null>(null)

const mobileTab = ref<MobileTab>('chat')

const DEFAULT_COLOR = '#f59e0b'

export interface ActiveAgentItem {
  role: string
  name: string
  color: string
}

const isAteneaDebateFlow = computed(() => {
  return !store.selectedAgent || store.selectedAgent === 'supervisor' || store.selectedAgent === 'atenea'
})

const isOrbDebating = computed(() => {
  if (store.isHitlRequired && !store.isTtsPlaying) {
    return false
  }
  return store.isDebating || store.isTtsPlaying || Boolean(store.readingAgentRoles && store.readingAgentRoles.length > 0)
})

function getAgentRoleNorm(role: string): string {
  return (store.normalizeAgentRole ? store.normalizeAgentRole(role) : role).toLowerCase()
}

function resolveAgentItem(role: string, ateneaColor: string): ActiveAgentItem {
  const ag = store.findAgent ? store.findAgent(role) : store.agents.find(a => a.role === role)
  const norm = getAgentRoleNorm(role)
  const isAtenea = norm === 'supervisor' || norm === 'atenea'

  return {
    role,
    name: ag?.name || (isAtenea ? 'Atenea' : role),
    color: ag?.color_hex || (isAtenea ? ateneaColor : DEFAULT_COLOR)
  }
}

function appendAgentIfMissing(list: ActiveAgentItem[], item: ActiveAgentItem) {
  const normTarget = getAgentRoleNorm(item.role)
  const exists = list.some(r => getAgentRoleNorm(r.role) === normTarget)
  if (!exists) {
    list.push(item)
  }
}

function appendRoleIfMissing(list: ActiveAgentItem[], role: string, ateneaColor: string) {
  appendAgentIfMissing(list, resolveAgentItem(role, ateneaColor))
}

function appendRolesIfMissing(list: ActiveAgentItem[], roles: string[] | undefined, ateneaColor: string) {
  if (!roles || roles.length === 0) return
  for (const role of roles) {
    appendRoleIfMissing(list, role, ateneaColor)
  }
}

const activeAgentsList = computed<ActiveAgentItem[]>(() => {
  // If waiting at HITL and no one is speaking TTS, orb is in idle mode
  if (store.isHitlRequired && !store.isTtsPlaying) {
    return []
  }

  const supervisorAgent = store.findAgent ? store.findAgent('supervisor') : store.agents.find(a => a.role === 'supervisor')
  const ateneaColor = supervisorAgent?.color_hex || '#f59e0b'
  const isDebatingOrTts = store.isDebating || store.isTtsPlaying || Boolean(store.readingAgentRoles?.length)

  const result: ActiveAgentItem[] = []

  // In an Atenea debate flow, Atenea is the overarching supervisor delegating to council agents,
  // so she is ALWAYS present in the active orb deliberation alongside delegated specialists.
  if (isAteneaDebateFlow.value && isDebatingOrTts) {
    result.push({
      role: 'supervisor',
      name: 'Atenea',
      color: ateneaColor
    })
  }
  
  if (store.activeTtsRole) {
    appendRoleIfMissing(result, store.activeTtsRole, ateneaColor)
  }

  // Include any agents currently reading their messages
  appendRolesIfMissing(result, store.readingAgentRoles, ateneaColor)

  // If multiple agents were chosen in the multi-agent selector, keep all selected agents active on the orb
  if (isDebatingOrTts && store.selectedAgents && store.selectedAgents.length > 1) {
    appendRolesIfMissing(result, store.selectedAgents, ateneaColor)
  }

  for (const agent of store.agents) {
    if (agent.state === 'ACTIVE') {
      appendAgentIfMissing(result, {
        role: agent.role,
        name: agent.name || agent.role,
        color: agent.color_hex || DEFAULT_COLOR
      })
    }
  }

  if (result.length === 0 && isDebatingOrTts) {
    result.push({
      role: 'supervisor',
      name: 'Atenea',
      color: ateneaColor
    })
  }

  return result
})

const activeAgentColor = computed(() => {
  if (store.activeTtsRole) {
    const ttsAgent = store.findAgent ? store.findAgent(store.activeTtsRole) : store.agents.find(a => a.role === store.activeTtsRole)
    if (ttsAgent?.color_hex) return ttsAgent.color_hex
    if (store.activeTtsRole === 'supervisor' || store.activeTtsRole.toLowerCase() === 'atenea') return '#f59e0b'
    return DEFAULT_COLOR
  }
  
  const delegatedAgent = store.agents.find(a => a.state === 'ACTIVE' && a.role !== 'supervisor')
  if (delegatedAgent?.color_hex) {
    return delegatedAgent.color_hex
  }

  const activeAgent = store.agents.find(a => a.state === 'ACTIVE')
  if (activeAgent?.color_hex) return activeAgent.color_hex

  return DEFAULT_COLOR
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
    requestAnimationFrame(() => {
      particleOrbRef.value?.resizeCanvas?.()
    })
  }
}

const isMobileViewport = ref(typeof window !== 'undefined' ? window.innerWidth < 768 : false)
const updateViewport = () => {
  if (typeof window !== 'undefined') {
    isMobileViewport.value = window.innerWidth < 768
  }
}

onMounted(() => {
  updateViewport()
  window.addEventListener('resize', updateViewport)
})

onUnmounted(() => {
  window.removeEventListener('resize', updateViewport)
})

const handleToggleMic = () => {
  if (typeof window !== 'undefined' && window.innerWidth < 768) {
    mobileSoundBarRef.value?.toggleRecording?.()
  } else {
    particleOrbRef.value?.toggleRecording?.()
  }
}
</script>

<template>
  <div class="h-screen h-[100svh] max-h-[100dvh] w-full bg-space-950 flex flex-col overflow-hidden text-slate-900 dark:text-slate-300 font-sans">
    
    <!-- Top Header -->
    <AppHeader />

    <!-- Responsive Workspace: 1-Col Mobile / 2-Col Grid Tablet (Hero Centerpiece Top + Split Bottom) / 3-Col Desktop (>= 1280px) -->
    <div
      data-test="shell-workspace-grid"
      class="flex-1 flex flex-col md:grid md:grid-cols-2 md:grid-rows-[minmax(260px,38%)_1fr] xl:flex xl:flex-row overflow-hidden relative min-h-0"
    >
      <!-- Chat Panel (Mobile: Tab 'chat' / Tablet: Bottom-Left Col 1 Row 2 / Desktop: Left Column) -->
      <div
        data-test="shell-left-column"
        :class="mobileTab === 'chat' ? 'flex' : 'hidden'"
        class="w-full md:flex md:col-span-1 md:row-start-2 md:h-full xl:w-[380px] 2xl:w-[400px] xl:shrink-0 xl:order-1 flex-1 md:flex-none xl:h-full z-10 flex-col overflow-hidden min-h-0 md:border-r border-space-800"
      >
        <ChatPanel 
          ref="chatPanelRef"
          class="flex-1 min-h-0"
          :messages="store.messages"
          :is-debating="store.isDebating"
          @toggle-mic="handleToggleMic"
        />
      </div>

      <!-- Particle Orb (Mobile: Tab 'voice' / Tablet: Top Hero Centerpiece Col-Span-2 Row 1 / Desktop: Center Column) -->
      <div
        data-test="shell-orb-column"
        :class="mobileTab === 'voice' ? 'flex' : 'hidden'"
        class="w-full flex-1 md:flex-none xl:flex-1 h-full md:flex md:col-span-2 md:row-start-1 md:h-full xl:order-2 xl:h-full relative z-0 flex-col bg-[#04070d] min-h-0 overflow-hidden md:border-b xl:border-b-0 border-space-800"
      >
        <ParticleOrb 
          ref="particleOrbRef"
          :active-agent-color="activeAgentColor"
          :active-agents="activeAgentsList"
          :is-debating="isOrbDebating"
          :is-visible="!isMobileViewport || mobileTab === 'voice'"
          @submit-draft="chatPanelRef?.onSubmit()"
          class="flex-1 w-full h-full"
        />
      </div>

      <!-- Agent Topology & Observability (Mobile: Tab 'agents' or 'telemetry' / Tablet: Bottom-Right Col 2 Row 2 / Desktop: Right Column) -->
      <div
        data-test="shell-agents-column"
        :class="(mobileTab === 'agents' || mobileTab === 'telemetry') ? 'flex' : 'hidden'"
        class="w-full md:flex md:col-span-1 md:row-start-2 md:h-full xl:w-[380px] 2xl:w-[400px] xl:shrink-0 xl:order-3 flex-1 md:flex-none xl:h-full z-10 bg-space-900/50 backdrop-blur-md flex-col min-h-0"
      >
        <AgentTopology 
          ref="agentTopologyRef"
          class="flex-1" 
          :agents="store.agents"
          :initial-tab="mobileTab === 'telemetry' ? 'observability' : 'agents'"
          :is-visible="!isMobileViewport || mobileTab === 'agents' || mobileTab === 'telemetry'"
        >
          <template #orchestration>
            <div class="flex flex-col justify-center space-y-2 h-full">
              <h3 class="text-[10px] font-mono text-slate-500 uppercase tracking-widest">
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

    <!-- Mobile SoundBar Dock (Conditionally mounted only on mobile viewports so SoundBar is never duplicated) -->
    <div
      v-if="isMobileViewport"
      data-test="mobile-sound-bar"
      class="md:hidden w-full relative z-20 shrink-0 h-[34px]"
    >
      <SoundBar
        ref="mobileSoundBarRef"
        :active-agent-color="activeAgentColor"
        :is-debating="isOrbDebating"
        :collapsible="true"
        :initial-collapsed="true"
        :show-view-switch="false"
        :listen-wake-word="isMobileViewport"
        @submit-draft="chatPanelRef?.onSubmit()"
      />
    </div>

    <!-- Mobile Bottom Navigation Bar (< 768px) -->
    <nav
      data-test="mobile-bottom-nav"
      aria-label="Navegación principal móvil"
      class="md:hidden border-t border-cyan-900/40 bg-[#080e1a]/95 backdrop-blur-md px-2 py-1 pb-[max(0.5rem,env(safe-area-inset-bottom))] flex items-center justify-around z-30 shrink-0"
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
