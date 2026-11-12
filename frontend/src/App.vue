<script setup lang="ts">
import { computed, inject, onMounted, ref, watch } from 'vue'
import { routeLocationKey, useRouter } from 'vue-router'
import { useDebateStore } from './stores/debate'
import { useConfigStore } from './stores/config'
import { useAuthStore } from './stores/auth'
import { useTheme } from './composables/useTheme'
import BackendUnavailable from './components/BackendUnavailable.vue'

const store = useDebateStore()
const configStore = useConfigStore()
const authStore = useAuthStore()
const { initTheme } = useTheme()
const route = inject(routeLocationKey, null)
const router = useRouter()
const isRetrying = ref(false)

const isAuthRoute = computed(() => {
  return route?.name === 'login' || route?.name === 'setup'
})

watch(
  () => store.projectName,
  (name) => {
    if (typeof document !== 'undefined' && name) {
      document.title = `${name}`
    }
  },
  { immediate: true }
)

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

const handleRetry = async () => {
  if (isRetrying.value) return
  isRetrying.value = true
  try {
    await authStore.checkAuth()
    if (authStore.isBackendAvailable) {
      void store.fetchTopology()
      if (authStore.isInitialized === false) {
        if (router) await router.push('/setup')
      } else if (authStore.isAuthenticated) {
        if (!store.isAgentsLoaded) {
          await initializeAppData()
        }
      } else if (router) {
        await router.push('/login')
      }
    }
  } finally {
    isRetrying.value = false
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
  void store.fetchTopology()
  if (authStore.isAuthenticated && !isAuthRoute.value) {
    await initializeAppData()
  }
})
</script>

<template>
  <BackendUnavailable
    v-if="authStore.isBackendAvailable === false"
    :is-retrying="isRetrying"
    @retry="handleRetry"
  />
  <div v-else-if="isAuthRoute || store.isAgentsLoaded" class="h-screen h-dvh w-full bg-space-950 overflow-hidden">
    <router-view />
  </div>
  <div v-else class="h-screen h-dvh w-full bg-space-950 flex items-center justify-center text-neon-cyan font-mono text-sm tracking-widest animate-pulse">
    INITIALIZING {{ store.projectName }}...
  </div>
</template>

<style>
/* Base styles managed in src/assets/main.css */
</style>
