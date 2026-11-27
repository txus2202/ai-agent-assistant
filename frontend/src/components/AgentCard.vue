<script setup lang="ts">
import { computed, ref, useId } from 'vue'
import { useConfigStore, type AgentConfig } from '../stores/config'

const props = withDefaults(defineProps<{
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
  variant?: 'default' | 'topology'
}>(), {
  variant: 'default'
})

const store = useConfigStore()

const uid = useId()
const providerId = `${uid}-provider`
const modelId = `${uid}-model`
const ragTopKId = `${uid}-rag-top-k`
const ragMinScoreId = `${uid}-rag-min-score`

const agentConfig = computed<AgentConfig>(() => {
  return store.agentsConfig.find(c => c.id === props.role) || {
    id: props.role,
    name: props.roleName || props.role,
    provider: '',
    model_name: '',
    rag_top_k: 5,
    rag_min_score: 0.3,
    description: '',
    color_hex: '#00e5ff'
  }
})

const pendingRagTopK = ref<number | null>(null)
const pendingRagMinScore = ref<number | null>(null)

const provider = computed({
  get: () => agentConfig.value.provider,
  set: (val) => {
    let defaultModel = ''
    const selectedProvider = store.providers.find(p => p.id === val)
    if (selectedProvider && selectedProvider.models.length > 0) {
      defaultModel = selectedProvider.models[0]?.id || ''
    }
    void store.updateAgentConfig(props.role, val, defaultModel)
  }
})

const modelName = computed({
  get: () => agentConfig.value.model_name,
  set: (val) => {
    void store.updateAgentConfig(props.role, provider.value, val)
  }
})

const ragTopK = computed(() => pendingRagTopK.value ?? agentConfig.value.rag_top_k ?? 5)
const ragMinScore = computed(() => pendingRagMinScore.value ?? agentConfig.value.rag_min_score ?? 0.3)

const handleRagTopKInput = (event: Event) => {
  const target = event.target as HTMLInputElement
  pendingRagTopK.value = Number(target.value)
}

const handleRagMinScoreInput = (event: Event) => {
  const target = event.target as HTMLInputElement
  pendingRagMinScore.value = Number(target.value)
}

const commitRagTopK = (event: Event) => {
  const target = event.target as HTMLInputElement
  const normalized = Number(target.value)
  pendingRagTopK.value = normalized
  void store.updateAgentConfig(
    props.role,
    provider.value,
    modelName.value,
    normalized,
    ragMinScore.value,
  )
}

const commitRagMinScore = (event: Event) => {
  const target = event.target as HTMLInputElement
  const normalized = Number(target.value)
  pendingRagMinScore.value = normalized
  void store.updateAgentConfig(
    props.role,
    provider.value,
    modelName.value,
    ragTopK.value,
    normalized,
  )
}

const isGlowActive = computed(() => props.state === 'ACTIVE')

const displayRole = computed(() => {
  if (props.roleName) return props.roleName
  return props.role.replaceAll('_', ' ').toUpperCase()
})

const agentDescription = computed(() => {
  return props.description || agentConfig.value.description || ''
})

const agentColor = computed(() => {
  return props.colorHex || agentConfig.value.color_hex || '#00e5ff'
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

const cardStyle = computed(() => {
  if (isGlowActive.value) {
    return { borderColor: agentColor.value, boxShadow: `0 0 20px ${agentColor.value}40, inset 0 0 15px ${agentColor.value}1a` }
  }
  if (props.state === 'ERROR') {
    return { borderColor: '#ef4444', boxShadow: '0 0 15px rgba(239, 68, 68, 0.2)' }
  }
  return {}
})

const statusDotClass = computed(() => {
  if (props.state === 'ACTIVE') return 'animate-pulse'
  if (props.state === 'ERROR') return 'bg-rose-500 border border-rose-400'
  if (props.variant === 'topology') return 'border border-white/20'
  return 'bg-slate-300 dark:bg-slate-700/80 border border-slate-400 dark:border-slate-600/50'
})

const statusDotStyle = computed(() => {
  if (props.state === 'ACTIVE') {
    return { backgroundColor: agentColor.value, boxShadow: `0 0 10px ${agentColor.value}` }
  }
  if (props.state === 'ERROR') {
    return { backgroundColor: '#ef4444', boxShadow: '0 0 8px #ef4444' }
  }
  if (props.variant === 'topology') {
    return { backgroundColor: agentColor.value }
  }
  return {}
})

const statusTagClass = computed(() => {
  if (props.state === 'ACTIVE') {
    return 'bg-cyan-500/15 text-cyan-300 border-cyan-500/40 animate-pulse'
  }
  if (props.state === 'ERROR') {
    return 'bg-rose-500/20 text-rose-400 border-rose-500/50'
  }
  return 'bg-slate-100 dark:bg-slate-800/80 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-700/60'
})

const statusTagText = computed(() => {
  if (props.state === 'ACTIVE') return 'ACTIVE CO-EXEC'
  if (props.state === 'ERROR') return 'ERROR'
  return props.state
})
</script>

<template>
  <div 
    data-test="card-container"
    class="relative flex flex-col justify-between overflow-hidden rounded-xl bg-space-850/80 border border-space-700/80 p-3.5 transition-all duration-300"
    :class="[
      variant === 'topology' ? 'min-h-[132px]' : 'h-[230px] min-h-[230px]',
      isGlowActive ? (glowClass || '') : '',
      state === 'ERROR' ? 'border-rose-500/60 bg-rose-950/20' : ''
    ]"
    :style="cardStyle"
  >
    <!-- Top Section: Header & Badges -->
    <div>
      <div class="flex items-center justify-between gap-2">
        <!-- Status dot and agent name -->
        <div class="flex items-center space-x-2 min-w-0">
          <div 
            class="h-2.5 w-2.5 shrink-0 rounded-full transition-all duration-300"
            :class="statusDotClass"
            :style="statusDotStyle"
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

        <!-- Custom Header Action (topology variant) or Status Tag -->
        <slot v-if="variant === 'topology' && $slots['header-action']" name="header-action" />
        <span 
          v-else
          class="shrink-0 text-[9px] font-mono px-2 py-0.5 rounded uppercase tracking-wider font-semibold border"
          :class="statusTagClass"
        >
          {{ statusTagText }}
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

      <!-- Agent Mission Description (Full in topology variant; clamped to max 3 lines in compact sidebar) -->
      <p 
        data-test="agent-description" 
        class="font-sans mt-1.5"
        :class="variant === 'topology' ? 'text-xs text-slate-300 leading-relaxed' : 'text-[11px] text-slate-400 leading-snug line-clamp-3'"
        :title="agentDescription"
      >
        {{ agentDescription }}
      </p>
    </div>

    <!-- Topology Variant Custom Footer -->
    <div v-if="variant === 'topology' && $slots.footer" class="pt-3 mt-3 border-t border-space-700/40">
      <slot name="footer" />
    </div>

    <!-- Default Runtime Middle / Bottom Controls & Metrics -->
    <div v-else-if="variant !== 'topology'">
      <!-- Progress Bar (Visible only when ACTIVE) -->
      <div v-if="state === 'ACTIVE'" data-test="progress-bar" class="h-1 w-full bg-space-800 rounded-full overflow-hidden mb-1">
        <div 
          class="h-full opacity-70 animate-[shimmer_2s_infinite]" 
          :class="colorClass"
          :style="{ backgroundColor: agentColor }"
        ></div>
      </div>

      <!-- RAG Retrieval Controls (Visible only for agents with uses_rag: true) -->
      <div
        v-if="isRag"
        data-test="rag-config-controls"
        class="pt-1.5 mb-2.5 border-t border-space-700/30 grid grid-cols-2 gap-2.5 items-center w-full"
      >
        <div class="flex flex-col min-w-0">
          <div class="flex items-center justify-between text-[9px] font-mono text-slate-400 leading-none mb-0.5">
            <label :for="ragTopKId" class="truncate cursor-pointer" title="Cantidad máxima de fragmentos recuperados de ChromaDB (0 desactiva RAG)">Chunks</label>
            <span class="text-cyan-300 font-bold" data-test="rag-top-k-value">{{ ragTopK === 0 ? 'OFF' : ragTopK }}</span>
          </div>
          <input
            :id="ragTopKId"
            :value="ragTopK"
            type="range"
            min="0"
            max="20"
            step="1"
            data-test="rag-top-k-slider"
            class="rag-slider w-full cursor-pointer"
            :style="{ '--slider-progress': `${(Number(ragTopK) / 20) * 100}%` }"
            :aria-valuetext="ragTopK === 0 ? 'Desactivado' : `${ragTopK} fragmentos`"
            title="Chunks (Top-K): 0 a 20"
            @input="handleRagTopKInput"
            @change="commitRagTopK"
          />
        </div>

        <div class="flex flex-col min-w-0">
          <div class="flex items-center justify-between text-[9px] font-mono text-slate-400 leading-none mb-0.5">
            <label :for="ragMinScoreId" class="truncate cursor-pointer" title="Índice mínimo de similitud semántica (0.00 a 1.00)">Proximidad</label>
            <span class="text-cyan-300 font-bold" data-test="rag-min-score-value">{{ Number(ragMinScore).toFixed(2) }}</span>
          </div>
          <input
            :id="ragMinScoreId"
            :value="ragMinScore"
            type="range"
            min="0"
            max="1"
            step="0.05"
            :disabled="ragTopK === 0"
            data-test="rag-min-score-slider"
            class="rag-slider w-full cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
            :style="{ '--slider-progress': `${Number(ragMinScore) * 100}%` }"
            :aria-valuetext="`${Number(ragMinScore).toFixed(2)} de similitud mínima`"
            title="Proximidad mínima (Min Score): 0.00 a 1.00"
            @input="handleRagMinScoreInput"
            @change="commitRagMinScore"
          />
        </div>
      </div>

      <!-- Config Selectors (Provider ~36%, Model flex-1) -->
      <div class="pt-2 border-t border-space-700/30 flex items-center gap-1.5 w-full">
        <label :for="providerId" class="sr-only">Proveedor de IA para {{ displayRole }}</label>
        <select 
          :id="providerId"
          v-model="provider" 
          data-test="provider-select"
          class="w-[36%] min-w-0 bg-space-800/90 border border-space-700 hover:border-cyan-500/40 rounded px-1.5 py-1 text-[10px] font-mono font-bold text-cyan-300 outline-none truncate cursor-pointer transition-colors"
          title="Provider"
        >
          <option value="" disabled :selected="!provider">-- Proveedor --</option>
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
          <option value="" disabled :selected="!modelName">-- Modelo --</option>
          <template v-for="p in store.providers" :key="p.id">
            <template v-if="provider === p.id">
              <option v-for="m in p.models" :key="m.id" :value="m.id">{{ m.name }}</option>
            </template>
          </template>
        </select>
      </div>

      <!-- Observability Metrics Badges (50% Tokens Left, 50% Latency & Turns Right) -->
      <div class="pt-1.5 mt-1 border-t border-space-800/60 grid grid-cols-2 items-center text-[10px] font-mono text-slate-400 w-full">
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

.rag-slider {
  --slider-track-size: 2px;
  --slider-thumb-size: 9px;
  --slider-track-radius: 999px;
  --slider-thumb-radius: 50%;
  --slider-track-color: rgba(51, 65, 85, 0.75);
  --slider-fill-color: #22d3ee;
  --slider-thumb-color: #22d3ee;

  -webkit-appearance: none;
  appearance: none;
  inline-size: 100%;
  block-size: 12px;
  margin: 0;
  padding: 0;
  border: 0;
  background: transparent;
}

.rag-slider:focus-visible {
  outline: 2px solid var(--slider-fill-color);
  outline-offset: 2px;
}

.rag-slider::-webkit-slider-runnable-track {
  block-size: var(--slider-track-size);
  border: 0;
  border-radius: var(--slider-track-radius);
  background: linear-gradient(
    to right,
    var(--slider-fill-color) var(--slider-progress, 0%),
    var(--slider-track-color) var(--slider-progress, 0%)
  );
}

.rag-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  inline-size: var(--slider-thumb-size);
  block-size: var(--slider-thumb-size);
  margin-block-start: calc((var(--slider-track-size) - var(--slider-thumb-size)) / 2);
  border: 0;
  border-radius: var(--slider-thumb-radius);
  background: var(--slider-thumb-color);
  box-shadow: 0 0 6px rgba(34, 211, 238, 0.45);
}

.rag-slider::-moz-range-track {
  block-size: var(--slider-track-size);
  border: 0;
  border-radius: var(--slider-track-radius);
  background: var(--slider-track-color);
}

.rag-slider::-moz-range-progress {
  block-size: var(--slider-track-size);
  border-radius: var(--slider-track-radius);
  background: var(--slider-fill-color);
}

.rag-slider::-moz-range-thumb {
  inline-size: var(--slider-thumb-size);
  block-size: var(--slider-thumb-size);
  border: 0;
  border-radius: var(--slider-thumb-radius);
  background: var(--slider-thumb-color);
  box-shadow: 0 0 6px rgba(34, 211, 238, 0.45);
}
</style>