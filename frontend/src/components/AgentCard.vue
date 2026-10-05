<script setup lang="ts">
import { computed } from 'vue'
import { useConfigStore } from '../stores/config'

const props = defineProps<{
  role: string
  roleName?: string
  state: 'STANDBY' | 'ACTIVE' | 'COMPLETED'
  colorClass: string
  glowClass: string
}>()

const store = useConfigStore()

const agentConfig = computed(() => {
  return store.agentsConfig.find(c => c.id === props.role) || { provider: 'gemini', model_name: 'gemini-1.5-flash' }
})

const provider = computed({
  get: () => agentConfig.value.provider,
  set: (val) => {
    let defaultModel = ''
    const selectedProvider = store.providers.find(p => p.id === val)
    if (selectedProvider && selectedProvider.models.length > 0) {
      defaultModel = selectedProvider.models[0].id
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
  return props.role.replace(/_/g, ' ').toUpperCase()
})
</script>

<template>
  <div 
    data-test="card-container"
    class="relative overflow-hidden rounded-xl bg-space-850/80 border border-space-700 p-4 transition-all duration-300"
    :class="[isGlowActive ? glowClass : '']"
  >
    <div class="flex items-center space-x-3">
      <!-- Status Dot -->
      <div 
        class="h-3 w-3 rounded-full"
        :class="[
          state === 'ACTIVE' ? 'animate-pulse bg-white' : '',
          state === 'COMPLETED' ? 'bg-space-700' : '',
          state === 'STANDBY' ? 'bg-space-700' : ''
        ]"
      ></div>
      
      <!-- Role and Status Text -->
      <div>
        <h3 class="font-mono text-sm tracking-wider" :class="colorClass">
          {{ displayRole }}
        </h3>
        <p class="text-xs text-slate-400 font-mono mt-1">
          {{ state }} {{ state === 'ACTIVE' ? 'CO-EXEC' : '' }}
        </p>
      </div>
    </div>

    <!-- Progress Bar (Visible only when ACTIVE) -->
    <div v-if="state === 'ACTIVE'" data-test="progress-bar" class="mt-4 h-1 w-full bg-space-800 rounded-full overflow-hidden">
      <div class="h-full bg-current opacity-50 animate-[shimmer_2s_infinite]" :class="colorClass"></div>
    </div>

    <!-- Config Selectors -->
    <div class="mt-4 pt-3 border-t border-space-700/50 flex flex-col gap-2">
      <div class="flex justify-between items-center">
        <label class="text-[10px] text-space-400 uppercase tracking-widest font-mono">Provider</label>
        <select 
          v-model="provider" 
          data-test="provider-select"
          class="bg-space-800/80 border border-space-600 rounded px-2 py-1 text-xs font-mono text-space-200 outline-none focus:border-cyan-500/50 transition-colors"
        >
          <option v-for="p in store.providers" :key="p.id" :value="p.id">{{ p.name }}</option>
        </select>
      </div>

      <div class="flex justify-between items-center">
        <label class="text-[10px] text-space-400 uppercase tracking-widest font-mono">Model</label>
        <select 
          v-model="modelName" 
          data-test="model-select"
          class="bg-space-800/80 border border-space-600 rounded px-2 py-1 text-xs font-mono text-space-200 outline-none focus:border-cyan-500/50 transition-colors max-w-[120px] truncate"
        >
          <template v-for="p in store.providers" :key="p.id">
            <template v-if="provider === p.id">
              <option v-for="m in p.models" :key="m.id" :value="m.id">{{ m.name }}</option>
            </template>
          </template>
        </select>
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
