<script setup lang="ts">
import { computed, inject, onMounted, watch } from 'vue'
import { routeLocationKey } from 'vue-router'
import { useDebateStore } from './stores/debate'
import { useConfigStore } from './stores/config'
import { useAuthStore } from './stores/auth'
import { useTheme } from './composables/useTheme'

const store = useDebateStore()
const configStore = useConfigStore()
const authStore = useAuthStore()
const { initTheme } = useTheme()
const route = inject(routeLocationKey, null)

const isAuthRoute = computed(() => {
  return route?.name === 'login' || route?.name === 'setup'
})

const initializeAppData = async () => {
  try {
    await Promise.all([
      configStore.loadProviders(),
      configStore.loadAgentsConfig()
    ])
    await store.loadAgents()
    if (import.meta.env.MODE !== 'test') {
      store.connect()
    }
  } catch (e) {
    console.error('Failed to load application data:', e)
  }
}

watch(
  () => authStore.isAuthenticated,
  (authenticated) => {
    if (authenticated) {
      if (!store.isAgentsLoaded) {
        void initializeAppData()
      } else if (import.meta.env.MODE !== 'test') {
        store.connect()
      }
    } else {
      store.disconnect()
      store.isAgentsLoaded = false
    }
  }
)

onMounted(async () => {
  initTheme()
  if (authStore.isAuthenticated && !isAuthRoute.value) {
    await initializeAppData()
  }
})
</script>

<template>
  <div v-if="isAuthRoute || store.isAgentsLoaded" class="h-screen w-full bg-space-950 overflow-hidden">
    <router-view />
  </div>
  <div v-else class="h-screen w-full bg-space-950 flex items-center justify-center text-neon-cyan font-mono text-sm tracking-widest animate-pulse">
    INITIALIZING {{ store.projectName }}...
  </div>
</template>

<style>
/* Base styles managed in src/assets/main.css */
</style>
