<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  role: string
  state: 'STANDBY' | 'ACTIVE' | 'COMPLETED'
  colorClass: string
  glowClass: string
}>()

const isGlowActive = computed(() => props.state === 'ACTIVE')
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
          {{ role.replace('_', ' ') }}
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
  </div>
</template>

<style scoped>
@keyframes shimmer {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}
</style>
