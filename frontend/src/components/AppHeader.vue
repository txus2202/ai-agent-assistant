<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useDebateStore } from '../stores/debate'
import { useAuthStore } from '../stores/auth'
import { Cpu, Volume2, VolumeX, History, Ear, EarOff, Sun, Moon, LogOut, Users, User as UserIcon, KeyRound, X } from '@lucide/vue'
import { useTheme } from '../composables/useTheme'
import packageJson from '../../package.json'
import UserManagementModal from './UserManagementModal.vue'

const router = useRouter()
const version = packageJson.version
const debateStore = useDebateStore()
const authStore = useAuthStore()
const { isDarkMode, toggleTheme } = useTheme()
const isUserModalOpen = ref(false)
const isChangePasswordOpen = ref(false)
const currentPassword = ref('')
const newPassword = ref('')
const confirmNewPassword = ref('')
const passwordError = ref<string | null>(null)
const passwordSuccess = ref<string | null>(null)

const openChangePasswordModal = () => {
  currentPassword.value = ''
  newPassword.value = ''
  confirmNewPassword.value = ''
  passwordError.value = null
  passwordSuccess.value = null
  isChangePasswordOpen.value = true
}

const handleChangePassword = async () => {
  passwordError.value = null
  passwordSuccess.value = null
  if (!currentPassword.value || !newPassword.value) {
    passwordError.value = 'Complete todos los campos'
    return
  }
  if (newPassword.value.length < 8) {
    passwordError.value = 'La nueva contraseña debe tener al menos 8 caracteres'
    return
  }
  if (newPassword.value !== confirmNewPassword.value) {
    passwordError.value = 'Las contraseñas nuevas no coinciden'
    return
  }
  const ok = await authStore.changePassword(currentPassword.value, newPassword.value)
  if (ok) {
    passwordSuccess.value = 'Contraseña actualizada correctamente'
    currentPassword.value = ''
    newPassword.value = ''
    confirmNewPassword.value = ''
  } else {
    passwordError.value = authStore.errorMessage || 'Error al actualizar la contraseña'
  }
}

const handleLogout = async () => {
  debateStore.clearSession()
  debateStore.stopTts()
  if (debateStore.isAutoListenEnabled) {
    debateStore.stopAutoListen()
  }
  await authStore.logout()
  router.push('/login')
}

const toggleAudio = () => {
  debateStore.isVoiceOutputEnabled = !debateStore.isVoiceOutputEnabled
  if (!debateStore.isVoiceOutputEnabled) {
    debateStore.stopTts() // stop immediately if muted
  } else {
    debateStore.unlockAudioContext()
  }
}

const toggleAutoListen = () => {
  if (debateStore.isAutoListenEnabled) {
    debateStore.stopAutoListen()
  } else {
    debateStore.startAutoListen()
  }
}
</script>

<template>
  <header class="h-14 border-b border-cyan-900/40 bg-space-900/90 backdrop-blur-md flex items-center justify-between z-30 shrink-0 w-full">
    <!-- Left branding & Status tag (centered relative to chat column on desktop) -->
    <div class="flex items-center justify-start xl:justify-center px-3 sm:px-4 xl:w-[380px] 2xl:w-[400px] xl:shrink-0 shrink-0">
      <span class="text-xs sm:text-sm font-mono font-bold tracking-widest uppercase text-slate-300 dark:text-cyan-100">SYSTEM CORE V{{ version }}</span>
    </div>

    <!-- Center App Title Banner -->
    <div class="hidden sm:flex flex-1 justify-center items-center h-full min-w-0 px-2">
      <div class="relative px-4 xl:px-8 pt-[5px] pb-[6px] bg-space-850 border border-cyan-500/30 rounded-t-sm shadow-[0_0_20px_rgba(0,229,255,0.08)] truncate">
        <div class="absolute -top-[1px] left-1/2 -translate-x-1/2 w-16 h-[2px] bg-cyan-400 shadow-[0_0_10px_#00e5ff]"></div>
        <h1 class="text-xs sm:text-sm font-semibold tracking-widest uppercase text-cyan-100 flex items-center justify-center space-x-2">
          <Cpu class="w-4 h-4 text-cyan-400 shrink-0" />
          <span class="font-bold tracking-widest">{{ debateStore.projectName }}</span>
        </h1>
        <div class="text-center hidden xl:block">
          <span class="text-[9px] text-cyan-300/70 font-mono font-normal tracking-normal lowercase">({{ debateStore.projectDescription }})</span>
        </div>
      </div>
    </div>

    <!-- Right System Action Controls (Theme, Audio, Auto-Listen, History) -->
    <div class="flex items-center justify-end xl:justify-center px-3 sm:px-4 xl:w-[380px] 2xl:w-[400px] xl:shrink-0 shrink-0 gap-2 sm:gap-3">
      <!-- Theme Switcher (On/Off Toggle with Moon / Sun icons) -->
      <button 
        type="button"
        @click="toggleTheme" 
        data-test="theme-toggle-btn"
        class="relative inline-flex items-center w-11 h-6 p-0.5 rounded-full transition-colors duration-300 focus:outline-none cursor-pointer shrink-0 border"
        :class="isDarkMode 
          ? 'bg-space-800 border-cyan-700/60 shadow-[0_0_8px_rgba(0,229,255,0.15)]' 
          : 'bg-amber-100 border-amber-300 shadow-sm'"
        :title="isDarkMode ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'"
        aria-label="Alternar modo oscuro / claro"
      >
        <span 
          class="flex items-center justify-center w-5 h-5 rounded-full transition-transform duration-300 transform shadow-sm"
          :class="isDarkMode 
            ? 'translate-x-0 bg-space-950 border border-cyan-400/80 text-cyan-300' 
            : 'translate-x-5 bg-white border border-amber-400 text-amber-500'"
        >
          <Moon v-if="isDarkMode" class="w-3 h-3 text-cyan-300" />
          <Sun v-else class="w-3 h-3 text-amber-500" />
        </span>
      </button>

      <!-- Action Icons (centered with system column on desktop) -->
      <div class="flex items-center space-x-1 sm:space-x-1.5 text-slate-400 pl-2 border-l border-space-800">
        <button 
          @click="toggleAudio"
          class="min-w-[34px] min-h-[34px] sm:min-w-0 sm:min-h-0 p-1.5 flex items-center justify-center rounded transition border border-transparent cursor-pointer"
          :class="debateStore.isVoiceOutputEnabled 
            ? 'text-amber-600 dark:text-amber-400 xl:text-amber-400 bg-amber-500/15 dark:bg-amber-900/30 xl:bg-amber-900/30 border-amber-500/50' 
            : 'text-slate-500 dark:text-slate-400 hover:text-amber-600 dark:hover:text-amber-400 xl:hover:text-amber-200 hover:bg-space-800 hover:border-amber-500/40 dark:hover:border-amber-800/60'"
          title="Toggle System Audio"
        >
          <VolumeX v-if="!debateStore.isVoiceOutputEnabled" class="w-4 h-4 text-slate-400" />
          <Volume2 v-else class="w-4 h-4" />
        </button>
        <button 
          @click="toggleAutoListen"
          class="min-w-[34px] min-h-[34px] sm:min-w-0 sm:min-h-0 p-1.5 flex items-center justify-center rounded transition border border-transparent cursor-pointer"
          :class="debateStore.isAutoListenEnabled 
            ? 'text-amber-600 dark:text-amber-400 xl:text-amber-400 bg-amber-500/15 dark:bg-amber-900/30 xl:bg-amber-900/30 border-amber-500/50' 
            : 'text-slate-500 dark:text-slate-400 hover:text-amber-600 dark:hover:text-amber-400 xl:hover:text-amber-200 hover:bg-space-800 hover:border-amber-500/40 dark:hover:border-amber-800/60'"
          title="Toggle Auto-Listen (Wake Word)"
        >
          <Ear v-if="debateStore.isAutoListenEnabled" class="w-4 h-4" />
          <EarOff v-else class="w-4 h-4" />
        </button>
        <button 
          @click="router.push('/history')"
          class="min-w-[34px] min-h-[34px] sm:min-w-0 sm:min-h-0 p-1.5 flex items-center justify-center text-slate-500 dark:text-slate-400 hover:text-amber-600 dark:hover:text-amber-400 xl:hover:text-amber-200 hover:bg-space-800 rounded transition border border-transparent hover:border-amber-500/40 dark:hover:border-amber-800/60 relative cursor-pointer" 
          title="Debate History"
        >
          <History class="w-4 h-4" />
        </button>

        <!-- Authenticated User & Logout -->
        <div v-if="authStore.isAuthenticated" class="flex items-center gap-1.5 pl-2 border-l border-space-800">
          <button
            v-if="authStore.isAdmin"
            @click="isUserModalOpen = true"
            data-test="manage-users-btn"
            class="min-w-[34px] min-h-[34px] sm:min-w-0 sm:min-h-0 p-1.5 flex items-center justify-center text-slate-500 hover:text-cyan-300 hover:bg-space-800 rounded transition border border-transparent hover:border-cyan-500/40 cursor-pointer"
            title="Gestión de Operadores"
          >
            <Users class="w-4 h-4 text-cyan-400" />
          </button>
          <span
            data-test="user-badge"
            class="hidden md:inline-flex items-center gap-1 px-2 py-0.5 rounded bg-space-800 border border-cyan-800/40 text-cyan-300 font-mono text-[10px] tracking-wider uppercase"
            :title="`Usuario: ${authStore.user?.username}`"
          >
            <UserIcon class="w-3 h-3 text-cyan-400" />
            <span class="max-w-[80px] truncate">{{ authStore.user?.username }}</span>
          </span>
          <button
            @click="openChangePasswordModal"
            data-test="change-password-btn"
            class="min-w-[34px] min-h-[34px] sm:min-w-0 sm:min-h-0 p-1.5 flex items-center justify-center text-slate-500 hover:text-cyan-300 hover:bg-space-800 rounded transition border border-transparent hover:border-cyan-500/40 cursor-pointer"
            title="Cambiar mi contraseña"
          >
            <KeyRound class="w-4 h-4" />
          </button>
          <button
            @click="handleLogout"
            data-test="logout-btn"
            class="min-w-[34px] min-h-[34px] sm:min-w-0 sm:min-h-0 p-1.5 flex items-center justify-center text-slate-500 hover:text-red-400 hover:bg-space-800 rounded transition border border-transparent hover:border-red-500/40 cursor-pointer"
            title="Cerrar Sesión"
          >
            <LogOut class="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  </header>

  <UserManagementModal
    :is-open="isUserModalOpen"
    @close="isUserModalOpen = false"
  />

  <dialog
    v-if="isChangePasswordOpen"
    open
    data-test="change-password-modal"
    class="fixed inset-0 z-[99999] bg-black/80 backdrop-blur-md flex items-center justify-center p-4 border-0 m-0 w-full h-full max-w-none max-h-none text-inherit"
    @click.self="isChangePasswordOpen = false"
  >
    <div class="w-full max-w-md bg-space-900 border border-cyan-500/40 rounded-xl shadow-[0_0_30px_rgba(0,229,255,0.15)] p-5 space-y-4">
      <div class="flex items-center justify-between border-b border-space-800 pb-3">
        <span class="text-xs font-mono font-bold uppercase tracking-wider text-cyan-300 flex items-center gap-2">
          <KeyRound class="w-4 h-4 text-cyan-400" />
          Cambiar Contraseña
        </span>
        <button
          type="button"
          @click="isChangePasswordOpen = false"
          class="p-1 text-slate-400 hover:text-cyan-300 cursor-pointer"
          aria-label="Cerrar"
        >
          <X class="w-4 h-4" />
        </button>
      </div>

      <div v-if="passwordError" data-test="change-password-error" class="p-2.5 rounded bg-red-950/60 border border-red-500/40 text-red-200 text-xs font-mono">
        {{ passwordError }}
      </div>
      <div v-if="passwordSuccess" data-test="change-password-success" class="p-2.5 rounded bg-emerald-950/60 border border-emerald-500/40 text-emerald-200 text-xs font-mono">
        {{ passwordSuccess }}
      </div>

      <form @submit.prevent="handleChangePassword" class="space-y-3">
        <div>
          <label class="block text-[11px] font-mono uppercase text-slate-300 mb-1">Contraseña Actual</label>
          <input
            v-model="currentPassword"
            data-test="current-password-input"
            type="password"
            required
            autocomplete="current-password"
            class="w-full bg-space-950 border border-cyan-800/60 focus:border-cyan-400 focus:outline-none rounded px-3 py-2 text-xs font-mono text-cyan-100"
          />
        </div>
        <div>
          <label class="block text-[11px] font-mono uppercase text-slate-300 mb-1">Nueva Contraseña (mín. 8 caracteres)</label>
          <input
            v-model="newPassword"
            data-test="new-password-input"
            type="password"
            required
            autocomplete="new-password"
            class="w-full bg-space-950 border border-cyan-800/60 focus:border-cyan-400 focus:outline-none rounded px-3 py-2 text-xs font-mono text-cyan-100"
          />
        </div>
        <div>
          <label class="block text-[11px] font-mono uppercase text-slate-300 mb-1">Confirmar Nueva Contraseña</label>
          <input
            v-model="confirmNewPassword"
            data-test="confirm-new-password-input"
            type="password"
            required
            autocomplete="new-password"
            class="w-full bg-space-950 border border-cyan-800/60 focus:border-cyan-400 focus:outline-none rounded px-3 py-2 text-xs font-mono text-cyan-100"
          />
        </div>
        <div class="flex justify-end gap-2 pt-2">
          <button
            type="button"
            @click="isChangePasswordOpen = false"
            class="px-3 py-1.5 text-xs font-mono text-slate-400 hover:text-slate-200 cursor-pointer"
          >
            Cerrar
          </button>
          <button
            type="submit"
            data-test="submit-change-password-btn"
            :disabled="authStore.isLoading"
            class="px-4 py-1.5 bg-cyan-600 hover:bg-cyan-500 text-space-950 font-mono font-bold text-xs uppercase rounded transition cursor-pointer"
          >
            Actualizar
          </button>
        </div>
      </form>
    </div>
  </dialog>
</template>
