<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useDebateStore } from '../stores/debate'
import { Cpu, ShieldCheck, User, Lock, KeyRound, AlertCircle, Sparkles } from '@lucide/vue'

const router = useRouter()
const authStore = useAuthStore()
const debateStore = useDebateStore()

onMounted(() => {
  if (!debateStore.topology) {
    void debateStore.fetchTopology()
  }
})

const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const setupToken = ref('')
const validationError = ref<string | null>(null)

const handleSetup = async () => {
  validationError.value = null
  const cleanUsername = username.value.trim()
  const cleanToken = setupToken.value.trim()

  if (!cleanUsername || !password.value.trim() || !confirmPassword.value.trim()) {
    validationError.value = 'Por favor, complete todos los campos'
    return
  }

  if (authStore.setupTokenRequired && !cleanToken) {
    validationError.value = 'Se requiere el token de configuración inicial (INITIAL_SETUP_TOKEN)'
    return
  }

  if (password.value.length < 8) {
    validationError.value = 'La contraseña debe tener al menos 8 caracteres'
    return
  }

  if (password.value !== confirmPassword.value) {
    validationError.value = 'Las contraseñas no coinciden'
    return
  }

  const success = await authStore.setupInitialAdmin(
    cleanUsername,
    password.value,
    cleanToken || undefined,
  )
  if (success) {
    await router.push('/')
  }
}
</script>

<template>
  <div class="min-h-screen min-h-dvh w-full bg-space-950 flex flex-col items-center justify-center p-4 relative overflow-hidden">
    <!-- Ambient ambient glow -->
    <div class="absolute -top-40 -right-40 w-96 h-96 bg-amber-500/10 rounded-full blur-3xl pointer-events-none"></div>
    <div class="absolute -bottom-40 -left-40 w-96 h-96 bg-cyan-600/10 rounded-full blur-3xl pointer-events-none"></div>

    <div class="w-full max-w-lg relative z-10">
      <!-- Header branding -->
      <div class="text-center mb-6">
        <div class="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-space-900 border border-amber-500/30 shadow-[0_0_25px_rgba(245,158,11,0.15)] mb-3">
          <Cpu class="w-8 h-8 text-amber-400 animate-pulse" />
        </div>
        <h1 class="text-xl sm:text-2xl font-bold tracking-widest uppercase font-mono text-cyan-100">
          {{ debateStore.projectName }}
        </h1>
        <p class="text-xs font-mono text-amber-300/80 tracking-wider mt-1 uppercase flex items-center justify-center gap-1.5">
          <Sparkles class="w-3.5 h-3.5" />
          Inicialización del Núcleo &bull; Primer Arranque
        </p>
      </div>

      <!-- Setup Card -->
      <div class="bg-space-900/90 border border-amber-500/30 rounded-xl p-6 sm:p-8 backdrop-blur-xl shadow-[0_10px_35px_rgba(0,0,0,0.5)]">
        <div class="border-b border-space-800 pb-4 mb-6">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs font-mono font-bold uppercase tracking-wider text-amber-400 flex items-center gap-2">
              <ShieldCheck class="w-4 h-4" />
              Creación de Cuenta Administrador
            </span>
            <span class="text-[10px] font-mono text-amber-400/70 border border-amber-500/40 px-2 py-0.5 rounded">PASO 1 / 1</span>
          </div>
          <p class="text-[11px] font-mono text-slate-400 leading-relaxed">
            No se ha detectado ningún usuario registrado en la base de datos. Cree la cuenta administradora raíz para asegurar el sistema.
          </p>
        </div>

        <!-- Alert message -->
        <div
          v-if="validationError || authStore.errorMessage"
          class="mb-5 p-3 rounded-lg bg-red-950/60 border border-red-500/40 text-red-200 text-xs font-mono flex items-center gap-2"
        >
          <AlertCircle class="w-4 h-4 text-red-400 shrink-0" />
          <span>{{ validationError || authStore.errorMessage }}</span>
        </div>

        <form @submit.prevent="handleSetup" class="space-y-4">
          <div>
            <label for="setup-username" class="block text-xs font-mono uppercase tracking-wider text-slate-300 mb-1.5 flex items-center gap-1.5">
              <User class="w-3.5 h-3.5 text-amber-400" />
              Usuario Administrador
            </label>
            <input
              id="setup-username"
              v-model="username"
              data-test="username"
              type="text"
              autocomplete="username"
              placeholder="admin"
              class="w-full px-3.5 py-2.5 bg-space-950 border border-space-800 focus:border-amber-400 focus:ring-1 focus:ring-amber-400 rounded-lg text-base sm:text-sm text-cyan-50 placeholder-slate-600 font-mono transition-colors outline-none"
            />
          </div>

          <div>
            <label for="setup-password" class="block text-xs font-mono uppercase tracking-wider text-slate-300 mb-1.5 flex items-center gap-1.5">
              <Lock class="w-3.5 h-3.5 text-amber-400" />
              Contraseña Maestra (Mínimo 8 caracteres)
            </label>
            <input
              id="setup-password"
              v-model="password"
              data-test="password"
              type="password"
              autocomplete="new-password"
              placeholder="••••••••••••"
              class="w-full px-3.5 py-2.5 bg-space-950 border border-space-800 focus:border-amber-400 focus:ring-1 focus:ring-amber-400 rounded-lg text-base sm:text-sm text-cyan-50 placeholder-slate-600 font-mono transition-colors outline-none"
            />
          </div>

          <div>
            <label for="setup-confirm-password" class="block text-xs font-mono uppercase tracking-wider text-slate-300 mb-1.5 flex items-center gap-1.5">
              <Lock class="w-3.5 h-3.5 text-amber-400" />
              Confirmar Contraseña
            </label>
            <input
              id="setup-confirm-password"
              v-model="confirmPassword"
              data-test="confirm-password"
              type="password"
              autocomplete="new-password"
              placeholder="••••••••••••"
              class="w-full px-3.5 py-2.5 bg-space-950 border border-space-800 focus:border-amber-400 focus:ring-1 focus:ring-amber-400 rounded-lg text-base sm:text-sm text-cyan-50 placeholder-slate-600 font-mono transition-colors outline-none"
            />
          </div>

          <div v-if="authStore.setupTokenRequired">
            <label for="setup-token" class="block text-xs font-mono uppercase tracking-wider text-amber-300 mb-1.5 flex items-center gap-1.5">
              <KeyRound class="w-3.5 h-3.5 text-amber-400" />
              Token de Inicialización (INITIAL_SETUP_TOKEN)
            </label>
            <input
              id="setup-token"
              v-model="setupToken"
              data-test="setup-token"
              type="password"
              autocomplete="off"
              placeholder="Token de seguridad del servidor"
              class="w-full px-3.5 py-2.5 bg-space-950 border border-amber-500/40 focus:border-amber-400 focus:ring-1 focus:ring-amber-400 rounded-lg text-base sm:text-sm text-cyan-50 placeholder-slate-600 font-mono transition-colors outline-none"
            />
          </div>

          <div class="pt-2">
            <button
              type="submit"
              :disabled="authStore.isLoading"
              class="w-full py-2.5 px-4 bg-amber-500/20 hover:bg-amber-500/30 border border-amber-400/50 hover:border-amber-400 text-amber-100 font-mono text-xs uppercase tracking-widest font-semibold rounded-lg transition-all duration-200 flex items-center justify-center gap-2 cursor-pointer shadow-[0_0_15px_rgba(245,158,11,0.15)] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ShieldCheck v-if="!authStore.isLoading" class="w-4 h-4 text-amber-300" />
              <span v-if="!authStore.isLoading">Inicializar y Proteger Sistema</span>
              <span v-else>Guardando configuración...</span>
            </button>
          </div>
        </form>
      </div>

      <!-- Footer Info -->
      <div class="mt-6 text-center text-[11px] font-mono text-slate-600 uppercase tracking-widest">
        Protección de acceso &bull; Argon2id + JWT + Cookies HttpOnly
      </div>
    </div>
  </div>
</template>

