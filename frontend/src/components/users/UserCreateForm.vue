<script setup lang="ts">
import { ref } from 'vue'
import { AlertCircle, CheckCircle2, ShieldCheck, UserPlus } from '@lucide/vue'

export interface CreateUserFormPayload {
  username: string
  password: string
  confirmPassword: string
  isAdmin: boolean
}

defineProps<{
  localError: string | null
  successMessage: string | null
  isSubmitting: boolean
  isStoreLoading: boolean
}>()

const emit = defineEmits<{
  (e: 'submit', payload: CreateUserFormPayload): void
}>()

const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const isAdmin = ref(false)

const resetFields = () => {
  username.value = ''
  password.value = ''
  confirmPassword.value = ''
  isAdmin.value = false
}

const onSubmit = () => {
  emit('submit', {
    username: username.value,
    password: password.value,
    confirmPassword: confirmPassword.value,
    isAdmin: isAdmin.value,
  })
}

defineExpose({
  resetFields,
})
</script>

<template>
  <div class="lg:col-span-5 flex flex-col gap-4 bg-space-950/50 p-5 rounded-lg border border-cyan-900/30">
    <div class="flex items-center gap-2 pb-2 border-b border-space-800">
      <UserPlus class="w-4 h-4 text-cyan-400" />
      <h3 class="text-xs font-mono font-bold uppercase tracking-wider text-cyan-200">
        Nuevo Operador
      </h3>
    </div>

    <div
      v-if="localError"
      data-test="error-banner"
      class="p-3 rounded bg-red-950/60 border border-red-500/40 text-red-200 text-xs font-mono flex items-start gap-2"
    >
      <AlertCircle class="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
      <span>{{ localError }}</span>
    </div>

    <div
      v-if="successMessage"
      data-test="success-banner"
      class="p-3 rounded bg-emerald-950/60 border border-emerald-500/40 text-emerald-200 text-xs font-mono flex items-start gap-2"
    >
      <CheckCircle2 class="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
      <span>{{ successMessage }}</span>
    </div>

    <form @submit.prevent="onSubmit" class="space-y-4">
      <div>
        <label
          for="new-operator-username"
          class="block text-[11px] font-mono uppercase tracking-wider text-slate-300 mb-1"
        >
          Nombre de Usuario
        </label>
        <div class="relative">
          <input
            id="new-operator-username"
            v-model="username"
            data-test="username-input"
            type="text"
            required
            autocomplete="off"
            placeholder="ej: operador_beta"
            class="w-full bg-space-900 border border-cyan-800/60 focus:border-cyan-400 focus:outline-none rounded px-3 py-2 text-base sm:text-xs font-mono text-cyan-100 placeholder-slate-600 transition"
          />
        </div>
      </div>

      <div>
        <label
          for="new-operator-password"
          class="block text-[11px] font-mono uppercase tracking-wider text-slate-300 mb-1"
        >
          Contraseña (mínimo 8 caracteres)
        </label>
        <div class="relative">
          <input
            id="new-operator-password"
            v-model="password"
            data-test="password-input"
            type="password"
            required
            autocomplete="new-password"
            placeholder="••••••••"
            class="w-full bg-space-900 border border-cyan-800/60 focus:border-cyan-400 focus:outline-none rounded px-3 py-2 text-base sm:text-xs font-mono text-cyan-100 placeholder-slate-600 transition"
          />
        </div>
      </div>

      <div>
        <label
          for="new-operator-confirm-password"
          class="block text-[11px] font-mono uppercase tracking-wider text-slate-300 mb-1"
        >
          Confirmar Contraseña
        </label>
        <div class="relative">
          <input
            id="new-operator-confirm-password"
            v-model="confirmPassword"
            data-test="confirm-password-input"
            type="password"
            required
            autocomplete="new-password"
            placeholder="••••••••"
            class="w-full bg-space-900 border border-cyan-800/60 focus:border-cyan-400 focus:outline-none rounded px-3 py-2 text-base sm:text-xs font-mono text-cyan-100 placeholder-slate-600 transition"
          />
        </div>
      </div>

      <div class="pt-1">
        <label class="flex items-center gap-2 cursor-pointer select-none">
          <input
            v-model="isAdmin"
            data-test="is-admin-checkbox"
            type="checkbox"
            class="rounded bg-space-900 border-cyan-700/60 text-cyan-400 focus:ring-0 focus:ring-offset-0 cursor-pointer"
          />
          <span class="text-xs font-mono text-slate-300 flex items-center gap-1.5">
            <ShieldCheck class="w-3.5 h-3.5 text-amber-400" />
            <span>Conceder rol de Administrador</span>
          </span>
        </label>
        <p class="text-[10px] font-mono text-slate-500 pl-6 mt-0.5">
          Los administradores pueden gestionar operadores y acceder a configuraciones globales.
        </p>
      </div>

      <div class="pt-2">
        <button
          type="submit"
          data-test="submit-user-btn"
          :disabled="isSubmitting || isStoreLoading"
          class="w-full py-2.5 px-4 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-space-950 font-mono font-bold text-xs uppercase tracking-wider rounded transition-all shadow-[0_0_15px_rgba(0,229,255,0.2)] flex items-center justify-center gap-2 cursor-pointer"
        >
          <UserPlus class="w-4 h-4" />
          <span>{{ isSubmitting ? 'REGISTRANDO...' : 'CREAR OPERADOR' }}</span>
        </button>
      </div>
    </form>
  </div>
</template>

