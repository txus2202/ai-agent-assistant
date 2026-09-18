<script setup lang="ts">
import { onMounted } from 'vue'
import AppShell from './components/AppShell.vue'
import { useDebateStore } from './stores/debate'

const store = useDebateStore()

onMounted(() => {
  store.loadAgents()
})
</script>

<template>
  <AppShell v-if="store.isAgentsLoaded" />
  <div v-else class="h-screen w-full bg-space-950 flex items-center justify-center text-neon-cyan font-mono text-sm tracking-widest animate-pulse">
    INITIALIZING A.T.E.N.E.A...
  </div>
</template>

<style>
/* Base styles managed in src/assets/main.css */
</style>
