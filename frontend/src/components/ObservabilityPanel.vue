<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { Activity, Terminal, Check, Database, ExternalLink } from '@lucide/vue'
import { useDebateStore, type Agent } from '../stores/debate'
import EventStream from './EventStream.vue'

const props = withDefaults(defineProps<{
  isVisible?: boolean
}>(), {
  isVisible: true
})

const debateStore = useDebateStore()

// System telemetry state
const cpuPercent = ref(38.0)
const memoryPercent = ref(62.0)
const clusterHealth = ref('HEALTHY')

const cpuHistory = ref<number[]>([25, 30, 28, 35, 40, 36, 42, 38, 44, 38])
const memoryHistory = ref<number[]>([58, 59, 60, 61, 60, 62, 63, 62, 64, 62])

let pollTimer: ReturnType<typeof setInterval> | null = null
let tickTimer: ReturnType<typeof setInterval> | null = null
let isComponentUnmounted = false
const isPageHidden = ref(typeof document !== 'undefined' ? document.visibilityState === 'hidden' : false)
const nowTick = ref(Date.now())
const isLangfuseEnabled = ref(
  import.meta.env.VITE_LANGFUSE_METRICS_ENABLED === 'true' ||
  import.meta.env.VITE_LANGFUSE_METRICS_ENABLED === true
)
const configuredDashboardUrl = ref<string>(
  import.meta.env.VITE_LANGFUSE_DASHBOARD_URL || ''
)

async function fetchStats() {
  try {
    const res = await fetch('/api/observability/stats')
    if (res.ok) {
      const data = await res.json()
      if (typeof data.cpu_percent === 'number' && data.cpu_percent >= 0) {
        cpuPercent.value = data.cpu_percent
        cpuHistory.value = [...cpuHistory.value.slice(1), data.cpu_percent]
      }
      if (typeof data.memory_percent === 'number' && data.memory_percent >= 0) {
        memoryPercent.value = data.memory_percent
        memoryHistory.value = [...memoryHistory.value.slice(1), data.memory_percent]
      }
      if (data.cluster_status) {
        clusterHealth.value = data.cluster_status
      }
      if (typeof data.langfuse_metrics_enabled === 'boolean') {
        isLangfuseEnabled.value = data.langfuse_metrics_enabled
      }
      if (typeof data.langfuse_dashboard_url === 'string' && data.langfuse_dashboard_url) {
        configuredDashboardUrl.value = data.langfuse_dashboard_url
      }
    }
  } catch {
    // Graceful fallback to local history
  }
}

// Dynamic thresholds per metric:
// < 70% -> Green, >= 70% and < 85% -> Amber/Orange, >= 85% -> Red
function getMetricTheme(value: number) {
  if (value >= 85) {
    return {
      stroke: '#ef4444',
      fill: 'rgba(239, 68, 68, 0.2)',
      textClass: 'text-red-500 font-bold',
      glowShadow: 'drop-shadow-[0_0_8px_rgba(239,68,68,0.5)]'
    }
  }
  if (value >= 70) {
    return {
      stroke: '#f59e0b',
      fill: 'rgba(245, 158, 11, 0.2)',
      textClass: 'text-amber-400 font-bold',
      glowShadow: 'drop-shadow-[0_0_8px_rgba(245,158,11,0.5)]'
    }
  }
  return {
    stroke: '#00ff9d',
    fill: 'rgba(0, 255, 157, 0.15)',
    textClass: 'text-neon-green font-bold',
    glowShadow: 'drop-shadow-[0_0_8px_rgba(0,255,157,0.3)]'
  }
}

const cpuTheme = computed(() => getMetricTheme(cpuPercent.value))
const memTheme = computed(() => getMetricTheme(memoryPercent.value))

function computeSparkline(data: number[], height = 24, width = 100) {
  if (data.length < 2) return { line: 'M 0 18 L 100 18', area: 'M 0 18 L 100 18 L 100 24 L 0 24 Z' }
  const step = width / (data.length - 1)
  const min = 0
  const max = 100
  const pts = data.map((val, i) => {
    const clamped = Math.max(min, Math.min(max, val))
    const y = height - ((clamped - min) / (max - min)) * (height - 6) - 3
    const x = i * step
    return { x: Math.round(x * 10) / 10, y: Math.round(y * 10) / 10 }
  })
  const line = pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ')
  const area = `${line} L ${width} ${height} L 0 ${height} Z`
  return { line, area }
}

const cpuSparkline = computed(() => computeSparkline(cpuHistory.value))
const memorySparkline = computed(() => computeSparkline(memoryHistory.value))

const DEFAULT_COLOR = '#00e5ff'

const displayAgents = computed(() => {
  const list = debateStore.agents || []
  return list.map(a => {
    const colorHex = a.color_hex || DEFAULT_COLOR
    const isReading = typeof debateStore.isAgentReading === 'function' ? debateStore.isAgentReading(a.role) : false
    const computedState = isReading ? 'ACTIVE' : a.state
    return {
      role: a.role,
      name: a.name || (a as { roleName?: string }).roleName || a.role,
      state: computedState,
      latency: a.latency,
      tokens: a.tokens,
      startedAt: a.startedAt,
      colorHex: colorHex,
      bgStyle: { backgroundColor: colorHex }
    }
  })
})

// Support multiple concurrently active agents (e.g. Innovator + Senior, or Diagrammer + DevOps)
const activeAgents = computed<Agent[]>(() => {
  return debateStore.agents?.filter(a => a.state === 'ACTIVE' || (typeof debateStore.isAgentReading === 'function' && debateStore.isAgentReading(a.role))) || []
})

const hasActiveAgents = computed(() => activeAgents.value.length > 0)
const isPanelActiveAndVisible = computed(() => !isComponentUnmounted && props.isVisible && !isPageHidden.value)
const shouldPollStats = computed(
  () => isPanelActiveAndVisible.value && (hasActiveAgents.value || Boolean(debateStore.isDebating))
)
const shouldTickNow = computed(() => isPanelActiveAndVisible.value && hasActiveAgents.value)

function stopPollTimer() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function stopTickTimer() {
  if (tickTimer) {
    clearInterval(tickTimer)
    tickTimer = null
  }
}

function syncPollingState() {
  if (shouldPollStats.value) {
    if (!pollTimer) {
      pollTimer = setInterval(() => {
        fetchStats().catch((err) => {
          console.error('Error polling stats:', err)
        })
      }, 3000)
    }
  } else {
    stopPollTimer()
  }
}

function syncTickState() {
  if (shouldTickNow.value) {
    nowTick.value = Date.now()
    if (!tickTimer) {
      tickTimer = setInterval(() => {
        nowTick.value = Date.now()
      }, 200)
    }
  } else {
    stopTickTimer()
  }
}

function handleVisibilityChange() {
  if (isComponentUnmounted || typeof document === 'undefined') return
  const wasHidden = isPageHidden.value
  isPageHidden.value = document.visibilityState === 'hidden'
  syncPollingState()
  syncTickState()
  if (wasHidden && !isPageHidden.value && props.isVisible) {
    fetchStats().catch((err) => {
      console.error('Error polling stats:', err)
    })
  }
}

watch(shouldPollStats, syncPollingState)
watch(shouldTickNow, syncTickState)
watch(
  () => props.isVisible,
  (visible, prevVisible) => {
    syncPollingState()
    syncTickState()
    if (visible && !prevVisible && !isPageHidden.value) {
      fetchStats().catch((err) => {
        console.error('Error polling stats:', err)
      })
    }
  }
)

onMounted(async () => {
  if (typeof document !== 'undefined') {
    isPageHidden.value = document.visibilityState === 'hidden'
    document.addEventListener('visibilitychange', handleVisibilityChange)
  }
  if (isPanelActiveAndVisible.value) {
    await fetchStats()
  }
  syncPollingState()
  syncTickState()
})

onUnmounted(() => {
  isComponentUnmounted = true
  if (typeof document !== 'undefined') {
    document.removeEventListener('visibilitychange', handleVisibilityChange)
  }
  stopPollTimer()
  stopTickTimer()
})

const activeAgentsTitle = computed(() => {
  if (activeAgents.value.length === 0) return 'STANDBY'
  return activeAgents.value
    .map(a => (a.name || (a as { roleName?: string }).roleName || a.role || '').toUpperCase())
    .join(' & ')
})

const clusterMetrics = computed(() => {
  const agents = displayAgents.value
  const total = agents.length || 1
  const completed = agents.filter(a => a.state === 'COMPLETED').length
  const hasError = agents.some(a => a.state === 'ERROR')
  const activeCount = activeAgents.value.length
  const isDebateRunning = debateStore.isDebating || activeCount > 0

  let percentage: number
  let statusText: string
  let strokeColor: string

  if (hasError && !isDebateRunning) {
    percentage = Math.round((completed / total) * 100)
    statusText = 'ERROR DETECTED'
    strokeColor = '#ef4444'
  } else if (isDebateRunning) {
    percentage = Math.min(100, Math.max(15, Math.round(((completed + (activeCount * 0.5)) / total) * 100)))
    statusText = 'AUDIT ONLINE'
    strokeColor = activeCount > 0 ? (displayAgents.value.find(a => a.state === 'ACTIVE')?.colorHex || '#00e5ff') : '#00e5ff'
  } else if (completed > 0 && completed === total) {
    percentage = 100.0
    statusText = 'CONSENSUS REACHED'
    strokeColor = '#00ff9d'
  } else {
    percentage = 99.8
    statusText = 'AUDIT ONLINE'
    strokeColor = '#00ff9d'
  }

  const dashoffset = 251.2 * (1 - (percentage / 100))

  return {
    percentage,
    statusText,
    strokeColor,
    dashoffset: Math.max(0, dashoffset)
  }
})

function getAgentStatusBadge(agent: { state: string; latency?: number; tokens?: number; startedAt?: number }) {
  if (agent.state === 'ACTIVE') {
    let elapsed: string
    if (agent.startedAt) {
      elapsed = ((nowTick.value - agent.startedAt) / 1000).toFixed(1)
    } else if (agent.latency) {
      elapsed = agent.latency.toFixed(1)
    } else {
      elapsed = '1.8'
    }

    return {
      text: `${elapsed}s running...`,
      badgeClass: 'text-[#ef4444] font-semibold animate-pulse',
      isLive: true
    }
  }
  if (agent.state === 'ERROR') {
    const lat = agent.latency !== undefined ? `${agent.latency.toFixed(2)}s` : 'Failed'
    return {
      text: `${lat} (Error)`,
      badgeClass: 'text-rose-400 font-semibold',
      isLive: false
    }
  }
  if (agent.state === 'COMPLETED') {
    const lat = agent.latency !== undefined ? `${agent.latency.toFixed(2)}s` : 'Completed'
    const tkn = agent.tokens ? ` (${agent.tokens} tkns)` : ''
    return {
      text: `${lat}${tkn}`,
      badgeClass: 'text-space-400 font-medium',
      isLive: false
    }
  }
  return {
    text: agent.latency !== undefined ? `${agent.latency.toFixed(2)}s (Idle)` : 'Standby',
    badgeClass: 'text-space-500 font-medium',
    isLive: false
  }
}

const langfuseDashboardUrl = computed(() => {
  if (configuredDashboardUrl.value) {
    return configuredDashboardUrl.value
  }
  if (typeof window !== 'undefined' && window.location) {
    const hostname = window.location.hostname
    return `http://${hostname}:3000`
  }
  return 'http://localhost:3000'
})

function openLangfuse(e: MouseEvent) {
  if (typeof window !== 'undefined') {
    window.open(langfuseDashboardUrl.value, '_blank', 'noopener,noreferrer')
    e.preventDefault()
  }
}
</script>

<template>
  <div class="flex-1 overflow-y-auto p-4 space-y-4 font-sans bg-[#060a11] text-space-200">
    
    <!-- Header: System Observability -->
    <div class="flex items-center justify-between pb-3 border-b border-space-800">
      <div class="flex items-center space-x-2">
        <Activity class="w-4 h-4 text-neon-green animate-pulse" />
        <h2 class="font-bold text-white text-[13px] tracking-wider font-mono">SYSTEM OBSERVABILITY</h2>
      </div>
      <div class="flex items-center space-x-1.5 px-2 py-0.5 rounded-full bg-neon-green/10 border border-neon-green/30">
        <span class="w-1.5 h-1.5 rounded-full bg-neon-green animate-ping"></span>
        <span class="text-neon-green font-mono text-[10px] font-bold tracking-widest">{{ clusterHealth }}</span>
      </div>
    </div>

    <!-- Cluster Gauge & Hardware Sparklines -->
    <div class="grid grid-cols-2 gap-3">
      <!-- Radial Cluster Gauge -->
      <div class="bg-[#080d16] border border-space-800 rounded p-4 flex flex-col items-center justify-center relative overflow-hidden">
        <div class="relative w-24 h-24 flex items-center justify-center">
          <svg class="w-full h-full -rotate-90" viewBox="0 0 100 100" aria-hidden="true">
            <!-- Background circle -->
            <circle
              cx="50"
              cy="50"
              r="40"
              fill="transparent"
              class="stroke-slate-800 dark:stroke-slate-800 light:stroke-slate-200"
              stroke="currentColor"
              stroke-width="8"
            />
            <!-- Progress circle -->
            <circle
              cx="50"
              cy="50"
              r="40"
              fill="transparent"
              :stroke="clusterMetrics.strokeColor"
              stroke-width="8"
              stroke-dasharray="251.2"
              :stroke-dashoffset="clusterMetrics.dashoffset"
              stroke-linecap="round"
              class="transition-all duration-500"
            />
          </svg>
          <div class="absolute flex flex-col items-center justify-center">
            <span class="text-white font-mono text-base font-extrabold">{{ clusterMetrics.percentage }}%</span>
            <span class="text-[8px] text-space-400 font-mono tracking-widest uppercase">CLUSTER</span>
          </div>
        </div>
        <div class="mt-2 text-center">
          <p
            class="font-mono text-[10px] font-bold tracking-widest uppercase transition-colors"
            :style="{ color: clusterMetrics.strokeColor }"
          >
            {{ clusterMetrics.statusText }}
          </p>
          <p class="text-space-400 font-mono text-[8px] tracking-widest mt-0.5 uppercase">
            {{ activeAgents.length > 0 ? activeAgentsTitle + ' ACTIVE' : 'CLUSTER READY' }}
          </p>
        </div>
      </div>

      <!-- CPU and Memory Sparklines with Independent Threshold Coloring -->
      <div class="bg-[#080d16] border border-space-800 rounded p-3 flex flex-col justify-between">
        <!-- CPU Load -->
        <div>
          <div class="flex items-center justify-between text-[10px] font-mono mb-1">
            <span class="text-space-400 uppercase tracking-wider">CPU LOAD (DUAL THREAD)</span>
            <span :class="cpuTheme.textClass">{{ cpuPercent.toFixed(1) }}%</span>
          </div>
          <div class="h-6 w-full bg-space-950/80 rounded border border-space-800/60 overflow-hidden relative">
            <svg class="w-full h-full" preserveAspectRatio="none" viewBox="0 0 100 24" aria-hidden="true">
              <path
                :d="cpuSparkline.area"
                :fill="cpuTheme.fill"
                class="transition-all duration-500"
              />
              <path
                :d="cpuSparkline.line"
                fill="none"
                :stroke="cpuTheme.stroke"
                stroke-width="1.5"
                class="transition-all duration-500"
              />
            </svg>
          </div>
        </div>

        <!-- Memory Usage -->
        <div class="mt-2">
          <div class="flex items-center justify-between text-[10px] font-mono mb-1">
            <span class="text-space-400 uppercase tracking-wider">MEMORY USAGE</span>
            <span :class="memTheme.textClass">{{ memoryPercent.toFixed(1) }}%</span>
          </div>
          <div class="h-6 w-full bg-space-950/80 rounded border border-space-800/60 overflow-hidden relative">
            <svg class="w-full h-full" preserveAspectRatio="none" viewBox="0 0 100 24" aria-hidden="true">
              <path
                :d="memorySparkline.area"
                :fill="memTheme.fill"
                class="transition-all duration-500"
              />
              <path
                :d="memorySparkline.line"
                fill="none"
                :stroke="memTheme.stroke"
                stroke-width="1.5"
                class="transition-all duration-500"
              />
            </svg>
          </div>
        </div>
      </div>
    </div>

    <!-- Agent Latency Benchmarks -->
    <div class="bg-[#080d16] border border-space-800 rounded p-3">
      <div class="flex items-center justify-between mb-3 text-[10px] font-mono">
        <span class="text-white font-bold tracking-wider uppercase">AGENT LATENCY BENCHMARKS</span>
        <span
          class="tracking-wider uppercase font-semibold"
          :class="activeAgents.length > 0 ? 'text-[#ef4444]' : 'text-neon-green'"
        >
          ACTIVE: {{ activeAgents.length }} ({{ activeAgentsTitle }})
        </span>
      </div>

      <div class="space-y-2.5 text-[10px] font-mono">
        <div v-for="agent in displayAgents" :key="agent.role">
          <div class="flex items-center justify-between mb-1">
            <span class="flex items-center space-x-1" :style="{ color: agent.colorHex }">
              <Check v-if="agent.state === 'COMPLETED'" class="w-3 h-3 text-neon-green" />
              <span v-else-if="agent.state === 'ACTIVE'" class="w-2 h-2 rounded-full animate-ping mr-0.5" :style="agent.bgStyle"></span>
              <span class="font-medium">{{ agent.name }}</span>
            </span>
            <span :class="getAgentStatusBadge(agent).badgeClass">
              {{ getAgentStatusBadge(agent).text }}
            </span>
          </div>
          <div class="w-full h-1.5 bg-space-950 rounded-full overflow-hidden">
            <div
              class="h-full rounded-full transition-all duration-300"
              :style="agent.bgStyle"
              :class="[
                agent.state === 'ACTIVE' ? 'w-3/4 animate-pulse shadow-[0_0_8px_currentColor]' : '',
                agent.state === 'COMPLETED' ? 'w-full opacity-85' : '',
                agent.state === 'STANDBY' ? 'w-1/4 opacity-25' : ''
              ]"
            ></div>
          </div>
        </div>
      </div>

      <!-- Context Caching & Token Efficiency Telemetry Card -->
      <div class="mt-3.5 pt-3 border-t border-space-800/80 bg-space-950/70 rounded p-2.5 font-mono text-[10px]">
        <div class="flex items-center justify-between mb-1.5">
          <span class="text-neon-cyan flex items-center space-x-1.5 font-bold tracking-wider uppercase">
            <Database class="w-3.5 h-3.5" />
            <span>SESSION CONTEXT CACHE</span>
          </span>
          <span class="text-neon-green font-bold tracking-wider">
            {{ debateStore.cacheSavingsPercentage ?? 0 }}% TOKENS AHORRADOS
          </span>
        </div>
        <div class="flex items-center justify-between text-[9px] text-space-400 mb-1">
          <span>Contexto reutilizado en sesión (RAG &amp; Prompts):</span>
          <span class="text-white font-semibold">{{ (debateStore.sessionCachedTokens ?? 0).toLocaleString() }} tkns</span>
        </div>
        <div class="w-full h-1.5 bg-space-900 rounded-full overflow-hidden">
          <div 
            class="h-full bg-gradient-to-r from-neon-cyan to-neon-green rounded-full transition-all duration-500"
            :style="{ width: `${Math.max(6, debateStore.cacheSavingsPercentage ?? 0)}%` }"
          ></div>
        </div>
      </div>
    </div>

    <!-- Unified Logs / Event Stream -->
    <div class="bg-[#080d16] border border-space-800 rounded p-3 flex flex-col">
      <div class="flex items-center justify-between mb-2 text-[10px] font-mono shrink-0">
        <div class="flex items-center space-x-1.5 text-white font-bold tracking-wider uppercase">
          <Terminal class="w-3.5 h-3.5 text-neon-cyan" />
          <span>LOGS / EVENT STREAM</span>
        </div>
        <span
          class="text-[9px] tracking-widest font-semibold flex items-center space-x-1"
          :class="activeAgents.length > 0 ? 'text-rose-400' : 'text-neon-green'"
        >
          <span
            class="w-1.5 h-1.5 rounded-full"
            :class="activeAgents.length > 0 ? 'bg-rose-500 animate-pulse' : 'bg-neon-green'"
          ></span>
          <span>{{ activeAgents.length > 0 ? activeAgentsTitle + '_ACTIVE' : 'STREAM READY' }}</span>
        </span>
      </div>

      <!-- Unified Real-Time Event Stream View (Scrollable on tablet, desktop, and mobile) -->
      <div class="bg-space-950/90 border border-space-800/60 rounded h-56 flex flex-col overflow-hidden">
        <EventStream :events="debateStore.rawEvents" class="flex-1 min-h-0" />
      </div>
    </div>

    <!-- Langfuse Dashboard External Link Button / Card -->
    <a
      v-if="isLangfuseEnabled"
      :href="langfuseDashboardUrl"
      target="_blank"
      rel="noopener noreferrer"
      data-test="langfuse-dashboard-link"
      @click="openLangfuse"
      class="flex items-center justify-between px-3 py-2 rounded bg-gradient-to-r from-[#0a1220] to-[#070d18] border border-cyan-500/30 hover:border-cyan-400/80 transition-all duration-300 group shadow-[0_0_12px_rgba(0,229,255,0.06)] hover:shadow-[0_0_16px_rgba(0,229,255,0.18)] cursor-pointer"
    >
      <div class="flex items-center space-x-2.5">
        <Activity class="w-3.5 h-3.5 text-neon-cyan group-hover:scale-110 transition-transform flex-shrink-0" />
        <span class="text-white font-mono text-[11px] font-bold tracking-wider uppercase">LANGFUSE TELEMETRY DASHBOARD</span>
      </div>
      <div class="flex items-center space-x-1.5 text-neon-cyan group-hover:translate-x-1 transition-transform pr-0.5">
        <span class="font-mono text-[10px] uppercase tracking-wider font-semibold">ABRIR</span>
        <ExternalLink class="w-3.5 h-3.5" />
      </div>
    </a>

  </div>
</template>
