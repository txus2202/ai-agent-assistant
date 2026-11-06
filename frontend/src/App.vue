<script setup lang="ts">
import { onMounted } from 'vue'
import { useDebateStore } from './stores/debate'
import { useConfigStore } from './stores/config'
import { useTheme } from './composables/useTheme'

const store = useDebateStore()
const configStore = useConfigStore()
const { initTheme } = useTheme()

onMounted(async () => {
  initTheme()
  await Promise.all([
    configStore.loadProviders(),
    configStore.loadAgentsConfig()
  ])
  await store.loadAgents()
})
</script>

<template>
  <div v-if="store.isAgentsLoaded" class="h-screen w-full bg-space-950 overflow-hidden">
    <router-view />
  </div>
  <div v-else class="h-screen w-full bg-space-950 flex items-center justify-center text-neon-cyan font-mono text-sm tracking-widest animate-pulse">
    INITIALIZING {{ store.projectName }}...
  </div>
</template>

<style>
/* Base styles managed in src/assets/main.css */
</style>
