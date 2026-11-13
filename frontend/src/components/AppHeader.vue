<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useDebateStore } from '../stores/debate'
import { useAuthStore } from '../stores/auth'
import { Cpu, Volume2, VolumeX, History, Ear, EarOff, Sun, Moon, LogOut, Users, User as UserIcon, KeyRound, X, ChevronDown } from '@lucide/vue'
import { useTheme } from '../composables/useTheme'
import UserManagementModal from './UserManagementModal.vue'

const router = useRouter()
const route = useRoute()
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
  await router.push('/login')
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

// User Profile Dropdown state & actions
const isUserMenuOpen = ref(false)
const userMenuRef = ref<HTMLElement | null>(null)

const displayUsername = computed(() => {
  const raw = authStore.user?.username || ''
  return raw.trim().split(/\s+/)[0] || ''
})

const toggleUserMenu = () => {
  isUserMenuOpen.value = !isUserMenuOpen.value
}

const openUserManagement = () => {
  isUserMenuOpen.value = false
  isUserModalOpen.value = true
}

const openChangePassword = () => {
  isUserMenuOpen.value = false
  openChangePasswordModal()
}

const handleUserLogout = async () => {
  isUserMenuOpen.value = false
  await handleLogout()
}

const handleClickOutsideUserMenu = (event: MouseEvent) => {
  if (!userMenuRef.value || !isUserMenuOpen.value) return
  const path = event.composedPath()
  if (!path.includes(userMenuRef.value)) {
    isUserMenuOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutsideUserMenu)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutsideUserMenu)
})
</script>

<template>
  <header class="border-b border-cyan-900/40 bg-space-900/90 backdrop-blur-md grid grid-cols-2 sm:flex sm:flex-row items-center sm:justify-between sm:min-h-14 sm:h-auto z-30 shrink-0 w-full relative pt-[max(0.625rem,env(safe-area-inset-top))] pb-2.5 sm:py-0 sm:pt-[env(safe-area-inset-top)] gap-y-4 sm:gap-y-0">
    <!-- Left Section: Operator Account Dropdown + Theme Switcher (Left-aligned with 16px padding & 16px gap across all viewports) -->
    <div
      data-test="header-left-section"
      class="col-span-1 order-2 sm:order-1 flex items-center justify-start pl-4 gap-4 xl:w-[380px] 2xl:w-[400px] xl:shrink-0 shrink-0"
    >
      <!-- Authenticated User Dropdown Menu -->
      <div v-if="authStore.isAuthenticated" ref="userMenuRef" class="relative">
        <button
          type="button"
          @click="toggleUserMenu"
          data-test="user-menu-btn"
          class="h-[34px] min-h-[34px] px-2 sm:px-2.5 rounded-lg border transition-all flex items-center gap-1.5 cursor-pointer text-slate-300 select-none"
          :class="isUserMenuOpen 
            ? 'border-cyan-400 bg-space-800 text-cyan-200 shadow-[0_0_12px_rgba(0,229,255,0.18)]' 
            : 'border-cyan-800/40 bg-space-850 hover:bg-space-800 hover:text-cyan-200 hover:border-cyan-500/50'"
          title="Menú de cuenta de operador"
          aria-haspopup="true"
          :aria-expanded="isUserMenuOpen"
        >
          <div class="w-5 h-5 rounded-full bg-space-900 border border-cyan-500/40 flex items-center justify-center text-cyan-400 shrink-0">
            <UserIcon class="w-3 h-3" />
          </div>
          
          <span
            data-test="user-badge"
            class="h-5 flex items-center font-mono text-[10px] sm:text-[11px] tracking-wider uppercase text-cyan-300 font-bold leading-none translate-y-[1px]"
          >
            <span class="max-w-[120px] sm:max-w-[150px] truncate inline-block">
              {{ displayUsername }}
            </span>
          </span>

          <ChevronDown class="w-3 h-3 text-slate-400 transition-transform duration-200 shrink-0" :class="{ 'rotate-180 text-cyan-400': isUserMenuOpen }" />
        </button>

        <!-- Dropdown Popover Menu -->
        <div
          v-if="isUserMenuOpen"
          data-test="user-menu-dropdown"
          class="absolute left-0 top-full mt-2 w-56 bg-space-900 border border-cyan-500/40 rounded-xl shadow-[0_12px_35px_rgba(0,0,0,0.7)] py-1.5 z-50 text-xs font-mono animate-fade-in backdrop-blur-md"
        >
          <!-- User Info Header -->
          <div class="px-3.5 py-2.5 border-b border-space-800 flex flex-col gap-0.5">
            <span class="text-[9px] uppercase tracking-widest text-slate-400">Operador Activo</span>
            <div class="flex items-center justify-between gap-2">
              <span class="text-xs font-bold text-cyan-100 truncate">{{ authStore.user?.username }}</span>
              <span
                class="px-1.5 py-0.5 rounded text-[8px] tracking-widest font-bold uppercase shrink-0"
                :class="authStore.isAdmin 
                  ? 'bg-amber-500/15 border border-amber-500/40 text-amber-300' 
                  : 'bg-cyan-500/15 border border-cyan-500/40 text-cyan-300'"
              >
                {{ authStore.isAdmin ? 'ADMIN' : 'OPERADOR' }}
              </span>
            </div>
          </div>

          <!-- Menu Actions -->
          <div class="py-1">
            <!-- Admin Only: Gestión de Operadores -->
            <button
              v-if="authStore.isAdmin"
              type="button"
              @click="openUserManagement"
              data-test="manage-users-btn"
              class="w-full px-3.5 py-2 text-left text-slate-300 hover:text-cyan-200 hover:bg-space-800/80 flex items-center gap-2.5 transition-colors cursor-pointer text-xs"
            >
              <Users class="w-4 h-4 text-cyan-400 shrink-0" />
              <span>Gestión de Operadores</span>
            </button>

            <!-- Cambiar Contraseña -->
            <button
              type="button"
              @click="openChangePassword"
              data-test="change-password-btn"
              class="w-full px-3.5 py-2 text-left text-slate-300 hover:text-cyan-200 hover:bg-space-800/80 flex items-center gap-2.5 transition-colors cursor-pointer text-xs"
            >
              <KeyRound class="w-4 h-4 text-slate-400 shrink-0" />
              <span>Cambiar mi contraseña</span>
            </button>
          </div>

          <!-- Divider -->
          <div class="border-t border-space-800 my-1"></div>

          <!-- Logout -->
          <div class="p-1">
            <button
              type="button"
              @click="handleUserLogout"
              data-test="logout-btn"
              class="w-full px-3 py-2 text-left text-red-400 hover:text-red-200 hover:bg-red-950/40 rounded-lg flex items-center gap-2.5 transition-colors cursor-pointer text-xs"
            >
              <LogOut class="w-4 h-4 text-red-400 shrink-0" />
              <span>Cerrar Sesión</span>
            </button>
          </div>
        </div>
      </div>

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
    </div>

    <!-- Center App Title Banner (Present in mobile at top centered with 16px gap to buttons, and in center on sm+) -->
    <div
      data-test="header-center-banner"
      class="col-span-2 sm:col-span-1 order-1 sm:order-2 flex sm:flex-1 justify-center items-center sm:h-full min-w-0 px-2"
    >
      <div class="relative px-5 sm:px-6 xl:px-8 py-2 sm:py-1.5 bg-space-850 border border-cyan-500/40 rounded-lg sm:rounded-t-sm shadow-[0_0_25px_rgba(0,229,255,0.12)] truncate">
        <div class="absolute -top-[1px] left-1/2 -translate-x-1/2 w-20 sm:w-24 h-[2px] bg-cyan-400 shadow-[0_0_12px_#00e5ff]"></div>
        <h1 class="text-sm sm:text-base font-semibold tracking-widest uppercase text-cyan-100 flex items-center justify-center space-x-2.5">
          <Cpu class="w-4 h-4 sm:w-4.5 sm:h-4.5 text-cyan-400 shrink-0" />
          <span class="font-bold tracking-widest">{{ debateStore.projectName }}</span>
        </h1>
        <div class="text-center hidden xl:block">
          <span class="text-[9px] text-cyan-300/70 font-mono font-normal tracking-normal lowercase">({{ debateStore.projectDescription }})</span>
        </div>
      </div>
    </div>

    <!-- Right System Action Controls (Audio, Auto-Listen, History) -->
    <div
      data-test="header-right-section"
      class="col-span-1 order-3 sm:order-3 flex items-center justify-end pr-4 gap-4 xl:w-[380px] 2xl:w-[400px] xl:shrink-0 shrink-0 text-slate-400"
    >
      <!-- Audio Output Button -->
      <button 
        type="button"
        @click="toggleAudio"
        data-test="toggle-audio-btn"
        class="h-[34px] min-h-[34px] w-[34px] min-w-[34px] rounded-lg border transition-all flex items-center justify-center cursor-pointer select-none group"
        :class="debateStore.isVoiceOutputEnabled 
          ? 'border-cyan-400 bg-space-800 text-cyan-200 shadow-[0_0_12px_rgba(0,229,255,0.18)]' 
          : 'border-cyan-800/40 bg-space-850 hover:bg-space-800 hover:text-cyan-200 hover:border-cyan-500/50 text-slate-400'"
        title="Toggle System Audio"
        aria-label="Toggle System Audio"
      >
        <Volume2 v-if="debateStore.isVoiceOutputEnabled" class="w-[18px] h-[18px] text-cyan-300" />
        <VolumeX v-else class="w-[18px] h-[18px] text-slate-400 group-hover:text-cyan-300 transition-colors" />
      </button>

      <!-- Auto-Listen (Wake Word) Button -->
      <button 
        type="button"
        @click="toggleAutoListen"
        data-test="toggle-autolisten-btn"
        class="h-[34px] min-h-[34px] w-[34px] min-w-[34px] rounded-lg border transition-all flex items-center justify-center cursor-pointer select-none group"
        :class="debateStore.isAutoListenEnabled 
          ? 'border-cyan-400 bg-space-800 text-cyan-200 shadow-[0_0_12px_rgba(0,229,255,0.18)]' 
          : 'border-cyan-800/40 bg-space-850 hover:bg-space-800 hover:text-cyan-200 hover:border-cyan-500/50 text-slate-400'"
        title="Toggle Auto-Listen (Wake Word)"
        aria-label="Toggle Auto-Listen (Wake Word)"
      >
        <Ear v-if="debateStore.isAutoListenEnabled" class="w-[18px] h-[18px] text-cyan-300" />
        <EarOff v-else class="w-[18px] h-[18px] text-slate-400 group-hover:text-cyan-300 transition-colors" />
      </button>

      <!-- History Navigation Button -->
      <button 
        type="button"
        @click="router.push('/history')"
        data-test="history-btn"
        class="h-[34px] min-h-[34px] w-[34px] min-w-[34px] rounded-lg border transition-all flex items-center justify-center cursor-pointer select-none group"
        :class="route?.path === '/history' 
          ? 'border-cyan-400 bg-space-800 text-cyan-200 shadow-[0_0_12px_rgba(0,229,255,0.18)]' 
          : 'border-cyan-800/40 bg-space-850 hover:bg-space-800 hover:text-cyan-200 hover:border-cyan-500/50 text-slate-400'"
        title="Debate History"
        aria-label="Debate History"
      >
        <History 
          class="w-[18px] h-[18px] transition-colors" 
          :class="route?.path === '/history' ? 'text-cyan-300' : 'text-slate-400 group-hover:text-cyan-300'"
        />
      </button>
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
    @cancel.prevent="isChangePasswordOpen = false"
    @keydown.esc="isChangePasswordOpen = false"
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
          <label for="header-current-password" class="block text-[11px] font-mono uppercase text-slate-300 mb-1">Contraseña Actual</label>
          <input
            id="header-current-password"
            v-model="currentPassword"
            data-test="current-password-input"
            type="password"
            required
            autocomplete="current-password"
            class="w-full bg-space-950 border border-cyan-800/60 focus:border-cyan-400 focus:outline-none rounded px-3 py-2 text-xs font-mono text-cyan-100"
          />
        </div>
        <div>
          <label for="header-new-password" class="block text-[11px] font-mono uppercase text-slate-300 mb-1">Nueva Contraseña (mín. 8 caracteres)</label>
          <input
            id="header-new-password"
            v-model="newPassword"
            data-test="new-password-input"
            type="password"
            required
            autocomplete="new-password"
            class="w-full bg-space-950 border border-cyan-800/60 focus:border-cyan-400 focus:outline-none rounded px-3 py-2 text-xs font-mono text-cyan-100"
          />
        </div>
        <div>
          <label for="header-confirm-password" class="block text-[11px] font-mono uppercase text-slate-300 mb-1">Confirmar Nueva Contraseña</label>
          <input
            id="header-confirm-password"
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
