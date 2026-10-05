<script setup lang="ts">
import { onMounted } from 'vue'
import { useDebateStore } from './stores/debate'
import { useConfigStore } from './stores/config'

const store = useDebateStore()
const configStore = useConfigStore()

onMounted(async () => {
  await Promise.all([
    configStore.loadProviders(),
    configStore.loadAgentsConfig()
  ])
  store.loadAgents()
})
</script>

<template>
  <div v-if="store.isAgentsLoaded" class="h-screen w-full bg-space-950 overflow-hidden">
    <router-view />
  </div>
  <div v-else class="h-screen w-full bg-space-950 flex items-center justify-center text-neon-cyan font-mono text-sm tracking-widest animate-pulse">
    INITIALIZING A.T.E.N.E.A...
  </div>
</template>

<style>
/* Base styles managed in src/assets/main.css */
</style>
