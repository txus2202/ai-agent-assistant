<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useDebateStore } from '../stores/debate'
import { Cpu, Lock, User, LogIn, AlertCircle } from '@lucide/vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const debateStore = useDebateStore()

onMounted(() => {
  if (!debateStore.topology) {
    void debateStore.fetchTopology()
  }
})

const username = ref('')
const password = ref('')
const validationError = ref<string | null>(null)

const handleLogin = async () => {
  validationError.value = null
  if (!username.value.trim() || !password.value.trim()) {
    validationError.value = 'Por favor, introduzca usuario y contraseña'
    return
  }

  const success = await authStore.login(username.value.trim(), password.value)
  if (success) {
    const rawRedirect = (route.query.redirect as string) || '/'
    const safeRedirect = rawRedirect.startsWith('/') && !rawRedirect.startsWith('//') ? rawRedirect : '/'
    await router.push(safeRedirect)
  }
}
</script>

<template>
  <div class="min-h-screen min-h-dvh w-full bg-space-950 flex flex-col items-center justify-center p-4 relative overflow-hidden">
    <!-- Cyberpunk ambient glowing background effects -->
    <div class="absolute -top-40 -left-40 w-96 h-96 bg-cyan-600/10 rounded-full blur-3xl pointer-events-none"></div>
    <div class="absolute -bottom-40 -right-40 w-96 h-96 bg-amber-500/10 rounded-full blur-3xl pointer-events-none"></div>

    <div class="w-full max-w-md relative z-10">
      <!-- Header branding -->
      <div class="text-center mb-6">
        <div class="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-space-900 border border-cyan-500/30 shadow-[0_0_25px_rgba(0,229,255,0.15)] mb-3">
          <Cpu class="w-8 h-8 text-cyan-400 animate-pulse" />
        </div>
        <h1 class="text-xl sm:text-2xl font-bold tracking-widest uppercase font-mono text-cyan-100">
          {{ debateStore.projectName }}
        </h1>
        <p class="text-xs font-mono text-cyan-300/70 tracking-wider mt-1 uppercase">
          Portal de Acceso
        </p>
      </div>

      <!-- Login Card -->
      <div class="bg-space-900/90 border border-cyan-900/60 rounded-xl p-6 sm:p-8 backdrop-blur-xl shadow-[0_10px_35px_rgba(0,0,0,0.5)]">
        <div class="border-b border-cyan-900/40 pb-4 mb-6 flex items-center justify-between">
          <span class="text-xs font-mono font-bold uppercase tracking-wider text-cyan-400 flex items-center gap-2">
            <Lock class="w-4 h-4" />
            Autenticación de Operador
          </span>
        </div>

        <!-- Alert messages -->
        <div
          v-if="validationError || authStore.errorMessage"
          class="mb-5 p-3 rounded-lg bg-red-950/60 border border-red-500/40 text-red-200 text-xs font-mono flex items-center gap-2"
        >
          <AlertCircle class="w-4 h-4 text-red-400 shrink-0" />
          <span>{{ validationError || authStore.errorMessage }}</span>
        </div>

        <form @submit.prevent="handleLogin" class="space-y-4">
          <div>
            <label for="login-username" class="block text-xs font-mono uppercase tracking-wider text-slate-300 mb-1.5 flex items-center gap-1.5">
              <User class="w-3.5 h-3.5 text-cyan-400" />
              Usuario
            </label>
            <input
              id="login-username"
              v-model="username"
              type="text"
              autocomplete="username"
              placeholder="Introduce tu usuario"
              class="w-full px-3.5 py-2.5 bg-space-950 border border-space-800 focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400 rounded-lg text-base sm:text-sm text-cyan-50 placeholder-slate-600 font-mono transition-colors outline-none"
            />
          </div>

          <div>
            <label for="login-password" class="block text-xs font-mono uppercase tracking-wider text-slate-300 mb-1.5 flex items-center gap-1.5">
              <Lock class="w-3.5 h-3.5 text-cyan-400" />
              Contraseña
            </label>
            <input
              id="login-password"
              v-model="password"
              type="password"
              autocomplete="current-password"
              placeholder="••••••••"
              class="w-full px-3.5 py-2.5 bg-space-950 border border-space-800 focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400 rounded-lg text-base sm:text-sm text-cyan-50 placeholder-slate-600 font-mono transition-colors outline-none"
            />
          </div>

          <div class="pt-2">
            <button
              type="submit"
              :disabled="authStore.isLoading"
              class="w-full py-2.5 px-4 bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-400/50 hover:border-cyan-400 text-cyan-100 font-mono text-xs uppercase tracking-widest font-semibold rounded-lg transition-all duration-200 flex items-center justify-center gap-2 cursor-pointer shadow-[0_0_15px_rgba(0,229,255,0.15)] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <LogIn v-if="!authStore.isLoading" class="w-4 h-4 text-cyan-300" />
              <span v-if="!authStore.isLoading">Iniciar Sesión</span>
              <span v-else>Autenticando...</span>
            </button>
          </div>
        </form>
      </div>

      <!-- Footer Info -->
      <div class="mt-6 text-center text-[11px] font-mono text-slate-600 uppercase tracking-widest">
        Acceso restringido &bull; {{ debateStore.projectName }} Multi-Agent System
      </div>
    </div>
  </div>
</template>

