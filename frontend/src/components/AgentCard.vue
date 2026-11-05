<script setup lang="ts">
import { computed, useId } from 'vue'
import { useConfigStore, type AgentConfig } from '../stores/config'
import { useTheme } from '../composables/useTheme'

const props = defineProps<{
  role: string
  roleName?: string
  description?: string
  colorHex?: string
  state: 'STANDBY' | 'ACTIVE' | 'COMPLETED' | 'ERROR'
  colorClass?: string
  glowClass?: string
  tokensConsumed?: number
  promptTokens?: number
  completionTokens?: number
  latencySeconds?: number
  turnsCount?: number
  usesRag?: boolean
  supportsHitl?: boolean
  canIngestDocuments?: boolean
  topologyRoles?: string[]
}>()

const store = useConfigStore()
const { isDarkMode } = useTheme()

const adaptColorForTheme = (hex: string, isDark: boolean): string => {
  if (isDark) return hex
  const lightMap: Record<string, string> = {
    '#00e5ff': '#0284c7', // Sky-600
    '#00ff9d': '#15803d', // Emerald-700
    '#ffd000': '#b45309', // Amber-700
    '#f59e0b': '#b45309', // Amber-700
    '#b347ff': '#7e22ce', // Purple-700
    '#ff8800': '#c2410c', // Orange-700
    '#ef4444': '#b91c1c', // Red-700
    '#2979ff': '#1d4ed8', // Blue-700
  }
  return lightMap[hex.toLowerCase()] || hex
}

const uid = useId()
const providerId = `${uid}-provider`
const modelId = `${uid}-model`

const agentConfig = computed<AgentConfig>(() => {
  return store.agentsConfig.find(c => c.id === props.role) || {
    id: props.role,
    name: props.roleName || props.role,
    provider: 'gemini',
    model_name: 'gemini-1.5-flash',
    description: '',
    color_hex: '#00e5ff'
  }
})

const provider = computed({
  get: () => agentConfig.value.provider,
  set: (val) => {
    let defaultModel = ''
    const selectedProvider = store.providers.find(p => p.id === val)
    if (selectedProvider && selectedProvider.models.length > 0) {
      defaultModel = selectedProvider.models[0]?.id || ''
    }
    store.updateAgentConfig(props.role, val, defaultModel)
  }
})

const modelName = computed({
  get: () => agentConfig.value.model_name,
  set: (val) => {
    store.updateAgentConfig(props.role, provider.value, val)
  }
})

const isGlowActive = computed(() => props.state === 'ACTIVE')

const displayRole = computed(() => {
  if (props.roleName) return props.roleName
  return props.role.replaceAll('_', ' ').toUpperCase()
})

const agentDescription = computed(() => {
  return props.description || agentConfig.value.description || ''
})

const agentColor = computed(() => {
  const base = props.colorHex || agentConfig.value.color_hex || '#00e5ff'
  return adaptColorForTheme(base, isDarkMode.value)
})

// Dynamic badges based on topology and capabilities
const computedRoles = computed(() => {
  return props.topologyRoles || agentConfig.value.topology_roles || []
})

const isRag = computed(() => {
  return props.usesRag ?? agentConfig.value.uses_rag ?? false
})

const isHitl = computed(() => {
  return props.supportsHitl ?? agentConfig.value.supports_hitl ?? false
})

const isDocs = computed(() => {
  return props.canIngestDocuments ?? agentConfig.value.can_ingest_documents ?? false
})
</script>

<template>
  <div 
    data-test="card-container"
    class="relative h-[230px] min-h-[230px] flex flex-col justify-between overflow-hidden rounded-xl bg-space-850/80 border border-space-700/80 p-3.5 transition-all duration-300"
    :class="[
      isGlowActive ? (glowClass || '') : '',
      state === 'ERROR' ? 'border-rose-500/60 bg-rose-950/20' : ''
    ]"
    :style="isGlowActive ? { borderColor: agentColor, boxShadow: `0 0 20px ${agentColor}40, inset 0 0 15px ${agentColor}1a` } : (state === 'ERROR' ? { borderColor: '#ef4444', boxShadow: '0 0 15px rgba(239, 68, 68, 0.2)' } : {})"
  >
    <!-- Top Section: Header & Badges -->
    <div>
      <div class="flex items-center justify-between gap-2">
        <!-- Status dot and agent name -->
        <div class="flex items-center space-x-2 min-w-0">
          <div 
            class="h-2.5 w-2.5 shrink-0 rounded-full transition-all duration-300"
            :class="[
              state === 'ACTIVE' ? 'animate-pulse' : (state === 'ERROR' ? 'bg-rose-500 border border-rose-400' : 'bg-slate-300 dark:bg-slate-700/80 border border-slate-400 dark:border-slate-600/50')
            ]"
            :style="state === 'ACTIVE' ? { backgroundColor: agentColor, boxShadow: `0 0 10px ${agentColor}` } : (state === 'ERROR' ? { backgroundColor: '#ef4444', boxShadow: '0 0 8px #ef4444' } : {})"
          ></div>
          <h3 
            class="font-mono text-xs font-bold tracking-wider truncate" 
            :class="colorClass"
            :style="{ color: state === 'ERROR' ? '#ef4444' : agentColor }"
            :title="displayRole"
          >
            {{ displayRole }}
          </h3>
        </div>

        <!-- Status Tag -->
        <span 
          class="shrink-0 text-[9px] font-mono px-2 py-0.5 rounded uppercase tracking-wider font-semibold border"
          :class="state === 'ACTIVE' 
            ? 'bg-cyan-500/15 text-cyan-300 border-cyan-500/40 animate-pulse' 
            : (state === 'ERROR' 
                ? 'bg-rose-500/20 text-rose-400 border-rose-500/50' 
                : 'bg-slate-100 dark:bg-slate-800/80 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-700/60')"
        >
          {{ state === 'ACTIVE' ? 'ACTIVE CO-EXEC' : (state === 'ERROR' ? 'ERROR' : state) }}
        </span>
      </div>

      <!-- Capability and Topology Badges -->
      <div class="flex flex-wrap gap-1 mt-1.5 items-center min-h-[18px]">
        <span 
          v-for="trole in computedRoles" 
          :key="trole"
          class="text-[9px] font-mono px-1.5 py-0.2 rounded border bg-space-800/90 text-slate-300 border-space-700 uppercase"
        >
          {{ trole }}
        </span>
        <span 
          v-if="isRag"
          class="text-[9px] font-mono px-1.5 py-0.2 rounded border bg-cyan-500/10 text-cyan-400 border-cyan-500/30 font-semibold"
        >
          RAG
        </span>
        <span 
          v-if="isHitl"
          class="text-[9px] font-mono px-1.5 py-0.2 rounded border bg-amber-500/10 text-amber-400 border-amber-500/30 font-semibold"
        >
          HITL
        </span>
        <span 
          v-if="isDocs"
          class="text-[9px] font-mono px-1.5 py-0.2 rounded border bg-indigo-500/10 text-indigo-400 border-indigo-500/30 font-semibold"
        >
          DOCS
        </span>
      </div>

      <!-- Agent Mission Description (Clamped to max 4 lines) -->
      <p 
        data-test="agent-description" 
        class="text-[11px] text-slate-400 font-sans leading-relaxed line-clamp-4 mt-1.5"
        :title="agentDescription"
      >
        {{ agentDescription }}
      </p>
    </div>

    <!-- Middle / Bottom Controls & Metrics -->
    <div>
      <!-- Progress Bar (Visible only when ACTIVE) -->
      <div v-if="state === 'ACTIVE'" data-test="progress-bar" class="h-1 w-full bg-space-800 rounded-full overflow-hidden mb-2">
        <div 
          class="h-full opacity-70 animate-[shimmer_2s_infinite]" 
          :class="colorClass"
          :style="{ backgroundColor: agentColor }"
        ></div>
      </div>

      <!-- Config Selectors (Provider ~36%, Model flex-1) -->
      <div class="pt-2 border-t border-space-700/50 flex items-center gap-1.5 w-full">
        <label :for="providerId" class="sr-only">Proveedor de IA para {{ displayRole }}</label>
        <select 
          :id="providerId"
          v-model="provider" 
          data-test="provider-select"
          class="w-[36%] min-w-0 bg-space-800/90 border border-space-700 hover:border-cyan-500/40 rounded px-1.5 py-1 text-[10px] font-mono font-bold text-cyan-300 outline-none truncate cursor-pointer transition-colors"
          title="Provider"
        >
          <option v-for="p in store.providers" :key="p.id" :value="p.id">{{ p.name }}</option>
        </select>

        <label :for="modelId" class="sr-only">Modelo de IA para {{ displayRole }}</label>
        <select 
          :id="modelId"
          v-model="modelName" 
          data-test="model-select"
          class="flex-1 min-w-0 bg-space-800/90 border border-space-700 hover:border-cyan-500/40 rounded px-1.5 py-1 text-[10px] font-mono font-bold text-cyan-300 outline-none truncate cursor-pointer transition-colors"
          title="Model"
        >
          <template v-for="p in store.providers" :key="p.id">
            <template v-if="provider === p.id">
              <option v-for="m in p.models" :key="m.id" :value="m.id">{{ m.name }}</option>
            </template>
          </template>
        </select>
      </div>

      <!-- Observability Metrics Badges (50% Tokens Left, 50% Latency & Turns Right) -->
      <div class="pt-2 mt-1 border-t border-space-800/80 grid grid-cols-2 items-center text-[10px] font-mono text-slate-400 w-full">
        <!-- Left Half (50%): Tokens In / Out -->
        <div 
          class="flex items-center space-x-1 justify-start min-w-0" 
          :title="`Tokens: Entrada ${promptTokens || 0} (Prompt) / Salida ${completionTokens !== undefined ? completionTokens : (tokensConsumed || 0)} (Generación)`"
        >
          <span class="shrink-0">🪙</span>
          <span class="text-emerald-400 font-semibold whitespace-nowrap" title="Tokens de entrada (Prompt)">
            <span class="text-[8px] text-slate-500 font-normal mr-0.5">In:</span>{{ promptTokens !== undefined ? promptTokens : 0 }}
          </span>
          <span class="text-slate-600 shrink-0">/</span>
          <span class="text-cyan-300 font-semibold whitespace-nowrap" title="Tokens de salida (Generación)">
            <span class="text-[8px] text-slate-500 font-normal mr-0.5">Out:</span>{{ completionTokens !== undefined ? completionTokens : (tokensConsumed || 0) }}
          </span>
        </div>

        <!-- Right Half (50%): Latency & Turns -->
        <div class="flex items-center justify-end space-x-2.5 sm:space-x-3 text-right min-w-0">
          <div class="flex items-center space-x-1 whitespace-nowrap" title="Latencia">
            <span class="shrink-0">⚡</span>
            <span class="text-slate-300 font-semibold">{{ latencySeconds !== undefined ? latencySeconds.toFixed(2) + 's' : '--' }}</span>
          </div>
          <div class="flex items-center space-x-1 whitespace-nowrap" title="Turnos de intervención">
            <span class="shrink-0">🔄</span>
            <span class="text-slate-300 font-semibold">{{ turnsCount !== undefined ? turnsCount : 0 }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@keyframes shimmer {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}
</style>