<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import {
  X,
  Users,
  UserPlus,
  Shield,
  ShieldCheck,
  KeyRound,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Edit2,
  Trash2,
  Power,
} from '@lucide/vue'
import { useAuthStore, type User } from '../stores/auth'
import { useDebateStore } from '../stores/debate'

const props = withDefaults(
  defineProps<{
    isOpen: boolean
    teleportDisabled?: boolean
  }>(),
  {
    teleportDisabled: false,
  },
)

const emit = defineEmits<{
  (e: 'close'): void
}>()

const debateStore = useDebateStore()

const isTestEnv = import.meta !== undefined && import.meta.env?.MODE === 'test'
const shouldDisableTeleport = computed(() => props.teleportDisabled || isTestEnv)

const authStore = useAuthStore()

// Form state (New User)
const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const isAdmin = ref(false)
const localError = ref<string | null>(null)
const successMessage = ref<string | null>(null)
const isSubmitting = ref(false)

// State for editing and deleting existing users
const editingUserId = ref<string | null>(null)
const editIsAdmin = ref(false)
const editPassword = ref('')
const confirmDeleteUserId = ref<string | null>(null)

const resetForm = () => {
  username.value = ''
  password.value = ''
  confirmPassword.value = ''
  isAdmin.value = false
  localError.value = null
  successMessage.value = null
  editingUserId.value = null
  editPassword.value = ''
  confirmDeleteUserId.value = null
}

const loadUsers = async () => {
  await authStore.fetchUsers()
}

watch(
  () => props.isOpen,
  async (newVal) => {
    if (newVal) {
      resetForm()
      await loadUsers()
    }
  },
  { immediate: true },
)

const handleKeyDown = (event: KeyboardEvent) => {
  if (event.key === 'Escape' && props.isOpen) {
    emit('close')
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeyDown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
})

const handleCreateUser = async () => {
  localError.value = null
  successMessage.value = null

  const cleanUsername = username.value.trim()
  if (!cleanUsername) {
    localError.value = 'El nombre de usuario es obligatorio'
    return
  }

  if (password.value.length < 8) {
    localError.value = 'La contraseña debe tener al menos 8 caracteres'
    return
  }

  if (password.value !== confirmPassword.value) {
    localError.value = 'Las contraseñas no coinciden'
    return
  }

  isSubmitting.value = true
  try {
    const created = await authStore.createUser(cleanUsername, password.value, isAdmin.value)
    if (created) {
      successMessage.value = `Operador creado correctamente: ${created.username}`
      username.value = ''
      password.value = ''
      confirmPassword.value = ''
      isAdmin.value = false
    } else {
      localError.value = authStore.errorMessage || 'No se pudo crear el operador'
    }
  } finally {
    isSubmitting.value = false
  }
}

const isSelf = (userId: string): boolean => {
  return authStore.user?.id === userId
}

const toggleUserActive = async (user: User) => {
  if (isSelf(user.id)) return
  localError.value = null
  successMessage.value = null
  const updated = await authStore.updateUser(user.id, { is_active: !user.is_active })
  if (updated) {
    successMessage.value = updated.is_active
      ? `Operador ${updated.username} activado`
      : `Operador ${updated.username} desactivado`
  } else {
    localError.value = authStore.errorMessage || 'Error al cambiar estado'
  }
}

const startEdit = (user: User) => {
  editingUserId.value = user.id
  editIsAdmin.value = user.is_admin
  editPassword.value = ''
  confirmDeleteUserId.value = null
  localError.value = null
  successMessage.value = null
}

const cancelEdit = () => {
  editingUserId.value = null
  editPassword.value = ''
}

const saveEdit = async (user: User) => {
  localError.value = null
  successMessage.value = null

  if (editPassword.value && editPassword.value.length < 8) {
    localError.value = 'La nueva contraseña debe tener al menos 8 caracteres'
    return
  }

  const payload: { is_admin?: boolean; password?: string } = {
    is_admin: editIsAdmin.value,
  }
  if (editPassword.value) {
    payload.password = editPassword.value
  }

  const updated = await authStore.updateUser(user.id, payload)
  if (updated) {
    successMessage.value = `Operador ${updated.username} actualizado correctamente`
    editingUserId.value = null
    editPassword.value = ''
  } else {
    localError.value = authStore.errorMessage || 'Error al actualizar operador'
  }
}

const promptDelete = (userId: string) => {
  if (isSelf(userId)) return
  confirmDeleteUserId.value = userId
  editingUserId.value = null
  localError.value = null
  successMessage.value = null
}

const cancelDelete = () => {
  confirmDeleteUserId.value = null
}

const confirmDelete = async (userId: string) => {
  localError.value = null
  successMessage.value = null
  const res = await authStore.deleteUser(userId)
  if (res.success) {
    successMessage.value =
      res.strategy === 'soft'
        ? 'Operador desactivado (soft delete)'
        : 'Operador eliminado permanentemente'
    confirmDeleteUserId.value = null
  } else {
    localError.value = authStore.errorMessage || 'Error al eliminar operador'
  }
}

const formatDate = (isoString: string): string => {
  try {
    const d = new Date(isoString)
    return d.toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return isoString
  }
}
</script>

<template>
  <Teleport to="body" :disabled="shouldDisableTeleport">
    <dialog
      v-if="isOpen"
      open
      data-test="user-management-modal-backdrop"
      class="fixed inset-0 z-[99999] bg-black/80 backdrop-blur-md flex flex-col items-center justify-center p-4 md:p-6 border-0 m-0 w-full h-full max-w-none max-h-none text-inherit"
      @click.self="emit('close')"
      @cancel.prevent="emit('close')"
      @keydown="handleKeyDown"
      aria-labelledby="user-modal-title"
      aria-modal="true"
    >
      <div
        class="w-full max-w-5xl max-h-[92vh] bg-space-900 border border-cyan-500/40 rounded-xl shadow-[0_0_40px_rgba(0,229,255,0.15)] flex flex-col overflow-hidden m-auto"
      >
        <!-- Modal Header -->
        <div
          class="flex items-center justify-between px-6 py-4 border-b border-space-800 bg-space-950/80"
        >
          <div class="flex items-center gap-3">
            <div
              class="w-9 h-9 rounded-lg bg-cyan-500/10 border border-cyan-500/40 flex items-center justify-center text-cyan-400 shadow-[0_0_12px_rgba(0,229,255,0.2)]"
            >
              <Users class="w-5 h-5" />
            </div>
            <div>
              <h2
                id="user-modal-title"
                class="text-sm font-mono font-bold text-white tracking-wider uppercase flex items-center gap-2"
              >
                <span>GESTIÓN DE OPERADORES</span>
                <span class="text-[10px] px-2 py-0.5 rounded bg-cyan-950 border border-cyan-500/30 text-cyan-400 font-mono">
                  ACCESO RESTRINGIDO
                </span>
              </h2>
              <p class="text-[11px] font-mono text-cyan-300/70 tracking-wide">
                Administración de credenciales, roles y ciclo de vida de operadores {{ debateStore.projectName }}.
              </p>
            </div>
          </div>

          <button
            type="button"
            @click="emit('close')"
            data-test="close-modal-btn"
            class="p-2 rounded-lg text-slate-400 hover:text-cyan-300 hover:bg-space-800 transition-colors cursor-pointer"
            title="Cerrar modal"
            aria-label="Cerrar modal"
          >
            <X class="w-5 h-5" />
          </button>
        </div>

        <!-- Modal Body: Two columns layout (Form + List) -->
        <div class="p-6 overflow-y-auto grid grid-cols-1 lg:grid-cols-12 gap-6 bg-space-900/60">
          <!-- Columna Izquierda: Formulario de Alta (5 cols) -->
          <div class="lg:col-span-5 flex flex-col gap-4 bg-space-950/50 p-5 rounded-lg border border-cyan-900/30">
            <div class="flex items-center gap-2 pb-2 border-b border-space-800">
              <UserPlus class="w-4 h-4 text-cyan-400" />
              <h3 class="text-xs font-mono font-bold uppercase tracking-wider text-cyan-200">
                Nuevo Operador
              </h3>
            </div>

            <!-- Feedback Alerts -->
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

            <form @submit.prevent="handleCreateUser" class="space-y-4">
              <div>
                <label for="new-operator-username" class="block text-[11px] font-mono uppercase tracking-wider text-slate-300 mb-1">
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
                <label for="new-operator-password" class="block text-[11px] font-mono uppercase tracking-wider text-slate-300 mb-1">
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
                <label for="new-operator-confirm-password" class="block text-[11px] font-mono uppercase tracking-wider text-slate-300 mb-1">
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
                  :disabled="isSubmitting || authStore.isLoading"
                  class="w-full py-2.5 px-4 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-space-950 font-mono font-bold text-xs uppercase tracking-wider rounded transition-all shadow-[0_0_15px_rgba(0,229,255,0.2)] flex items-center justify-center gap-2 cursor-pointer"
                >
                  <UserPlus class="w-4 h-4" />
                  <span>{{ isSubmitting ? 'REGISTRANDO...' : 'CREAR OPERADOR' }}</span>
                </button>
              </div>
            </form>
          </div>

          <!-- Columna Derecha: Lista de Operadores (7 cols) -->
          <div class="lg:col-span-7 flex flex-col gap-3 bg-space-950/30 p-5 rounded-lg border border-cyan-900/20">
            <div class="flex items-center justify-between pb-2 border-b border-space-800">
              <div class="flex items-center gap-2">
                <KeyRound class="w-4 h-4 text-cyan-400" />
                <h3 class="text-xs font-mono font-bold uppercase tracking-wider text-cyan-200">
                  Operadores Registrados ({{ authStore.users.length }})
                </h3>
              </div>
              <button
                type="button"
                @click="loadUsers"
                :disabled="authStore.usersLoading"
                class="flex items-center gap-1 text-[11px] font-mono text-slate-400 hover:text-cyan-300 transition-colors cursor-pointer"
                title="Actualizar lista"
              >
                <RefreshCw
                  class="w-3.5 h-3.5"
                  :class="{ 'animate-spin': authStore.usersLoading }"
                />
                <span>Refrescar</span>
              </button>
            </div>

            <!-- Loading indicator -->
            <div v-if="authStore.usersLoading" class="py-8 text-center text-xs font-mono text-cyan-400/80">
              Cargando operadores del sistema...
            </div>

            <!-- Empty state -->
            <div
              v-else-if="authStore.users.length === 0"
              class="py-8 text-center text-xs font-mono text-slate-500"
            >
              No hay operadores registrados.
            </div>

            <!-- Users List -->
            <div v-else class="space-y-3 max-h-[460px] overflow-y-auto pr-1">
              <div
                v-for="user in authStore.users"
                :key="user.id"
                data-test="user-item"
                class="p-3 rounded bg-space-900/80 border border-space-800 hover:border-cyan-800/40 flex flex-col gap-2 transition-colors"
              >
                <div class="flex items-center justify-between">
                  <!-- Left User info -->
                  <div class="flex items-center gap-3 min-w-0">
                    <div
                      class="w-7 h-7 rounded-full flex items-center justify-center font-mono text-xs font-bold shrink-0"
                      :class="user.is_admin ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30' : 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'"
                    >
                      {{ user.username.charAt(0).toUpperCase() }}
                    </div>
                    <div class="truncate">
                      <div class="flex items-center gap-2 flex-wrap">
                        <span class="text-xs font-mono font-bold text-cyan-100">
                          {{ user.username }}
                        </span>
                        <span
                          v-if="user.is_admin"
                          class="text-[9px] font-mono font-bold px-1.5 py-0.2 rounded bg-amber-950 text-amber-300 border border-amber-500/40 tracking-wider uppercase"
                        >
                          ADMINISTRADOR
                        </span>
                        <span
                          v-else
                          class="text-[9px] font-mono px-1.5 py-0.2 rounded bg-space-800 text-slate-400 border border-slate-700 tracking-wider uppercase"
                        >
                          OPERADOR
                        </span>
                        <span
                          v-if="user.deleted_at"
                          data-test="soft-deleted-badge"
                          class="text-[9px] font-mono font-bold px-1.5 py-0.2 rounded bg-red-950 text-red-300 border border-red-500/40 tracking-wider uppercase"
                        >
                          BAJA LÓGICA
                        </span>
                        <span v-if="isSelf(user.id)" class="text-[9px] font-mono text-cyan-400/80 italic">
                          (tú)
                        </span>
                      </div>
                      <div class="text-[10px] font-mono text-slate-500">
                        Alta: {{ formatDate(user.created_at) }}
                      </div>
                    </div>
                  </div>

                  <!-- Right Action controls -->
                  <div class="flex items-center gap-1.5 shrink-0">
                    <!-- Toggle Active / Inactive -->
                    <button
                      type="button"
                      @click="toggleUserActive(user)"
                      data-test="toggle-active-btn"
                      :disabled="isSelf(user.id) || authStore.isLoading"
                      class="px-2 py-0.5 rounded text-[10px] font-mono flex items-center gap-1 transition cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed border"
                      :class="user.is_active
                        ? 'bg-emerald-950/40 text-emerald-300 border-emerald-500/40 hover:bg-emerald-900/60'
                        : 'bg-red-950/40 text-red-300 border-red-500/40 hover:bg-red-900/60'"
                      :title="isSelf(user.id) ? 'No puedes desactivar tu propia cuenta' : (user.is_active ? 'Desactivar operador' : 'Activar operador')"
                    >
                      <Power class="w-3 h-3" />
                      <span>{{ user.is_active ? 'ACTIVO' : 'INACTIVO' }}</span>
                    </button>

                    <!-- Edit button -->
                    <button
                      type="button"
                      @click="startEdit(user)"
                      data-test="edit-user-btn"
                      class="p-1 rounded text-slate-400 hover:text-cyan-300 hover:bg-space-800 transition cursor-pointer"
                      title="Modificar operador"
                    >
                      <Edit2 class="w-3.5 h-3.5" />
                    </button>

                    <!-- Delete button -->
                    <button
                      type="button"
                      @click="promptDelete(user.id)"
                      data-test="delete-user-btn"
                      :disabled="isSelf(user.id) || authStore.isLoading"
                      class="p-1 rounded text-slate-400 hover:text-red-400 hover:bg-space-800 transition cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
                      :title="isSelf(user.id) ? 'No puedes eliminar tu propia cuenta' : 'Eliminar operador'"
                    >
                      <Trash2 class="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                <!-- Subsección Inline de Edición -->
                <div
                  v-if="editingUserId === user.id"
                  data-test="edit-user-form"
                  class="mt-2 p-3 rounded bg-space-950 border border-cyan-700/50 space-y-3 animate-fade-in"
                >
                  <div class="flex items-center justify-between pb-1 border-b border-space-800">
                    <span class="text-[11px] font-mono text-cyan-300 font-bold uppercase tracking-wider">
                      Modificar {{ user.username }}
                    </span>
                    <button
                      type="button"
                      @click="cancelEdit"
                      class="text-[10px] font-mono text-slate-400 hover:text-slate-200"
                    >
                      Cancelar
                    </button>
                  </div>

                  <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label class="flex items-center gap-2 cursor-pointer select-none">
                        <input
                          v-model="editIsAdmin"
                          data-test="edit-is-admin-checkbox"
                          type="checkbox"
                          :disabled="isSelf(user.id)"
                          class="rounded bg-space-900 border-cyan-700/60 text-cyan-400 focus:ring-0 cursor-pointer disabled:opacity-50"
                        />
                        <span class="text-xs font-mono text-slate-300">
                          Rol Administrador
                        </span>
                      </label>
                      <span v-if="isSelf(user.id)" class="text-[9px] font-mono text-slate-500 block">
                        (No puedes revocar tus propios privilegios)
                      </span>
                    </div>

                    <div>
                      <label :for="`edit-password-${user.id}`" class="sr-only">
                        Nueva contraseña (opcional)
                      </label>
                      <input
                        :id="`edit-password-${user.id}`"
                        v-model="editPassword"
                        data-test="edit-password-input"
                        type="password"
                        placeholder="Nueva contraseña (opcional)"
                        class="w-full bg-space-900 border border-cyan-800/60 focus:border-cyan-400 rounded px-2.5 py-1 text-base sm:text-xs font-mono text-cyan-100 placeholder-slate-600"
                      />
                    </div>
                  </div>

                  <div class="flex justify-end gap-2 pt-1">
                    <button
                      type="button"
                      @click="cancelEdit"
                      class="px-2.5 py-1 text-[11px] font-mono text-slate-400 hover:text-slate-200 cursor-pointer"
                    >
                      Descartar
                    </button>
                    <button
                      type="button"
                      @click="saveEdit(user)"
                      data-test="save-edit-btn"
                      :disabled="authStore.isLoading"
                      class="px-3 py-1 bg-cyan-600 hover:bg-cyan-500 text-space-950 font-mono font-bold text-xs rounded transition cursor-pointer"
                    >
                      Guardar Cambios
                    </button>
                  </div>
                </div>

                <!-- Subsección Inline de Confirmación de Borrado -->
                <div
                  v-if="confirmDeleteUserId === user.id"
                  data-test="confirm-delete-box"
                  class="mt-2 p-3 rounded bg-red-950/40 border border-red-500/50 space-y-2 animate-fade-in"
                >
                  <div class="text-xs font-mono text-red-200">
                    ¿Estás seguro de que deseas eliminar al operador <span class="font-bold underline">{{ user.username }}</span>?
                  </div>
                  <div class="text-[10px] font-mono text-slate-400">
                    La estrategia configurada se aplicará de acuerdo a la variable del entorno (soft-delete / hard-delete).
                  </div>
                  <div class="flex justify-end gap-2 pt-1">
                    <button
                      type="button"
                      @click="cancelDelete"
                      class="px-2.5 py-1 text-[11px] font-mono text-slate-400 hover:text-slate-200 cursor-pointer"
                    >
                      Cancelar
                    </button>
                    <button
                      type="button"
                      @click="confirmDelete(user.id)"
                      data-test="confirm-delete-btn"
                      :disabled="authStore.isLoading"
                      class="px-3 py-1 bg-red-600 hover:bg-red-500 text-white font-mono font-bold text-xs rounded transition cursor-pointer"
                    >
                      Confirmar Eliminación
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Modal Footer -->
        <div class="px-6 py-3 border-t border-space-800 bg-space-950/80 flex items-center justify-between text-[11px] font-mono text-slate-500">
          <span class="flex items-center gap-1.5">
            <Shield class="w-3.5 h-3.5 text-cyan-400" />
            <span>Las contraseñas se almacenan mediante Argon2id con sal criptográfica única.</span>
          </span>
          <button
            type="button"
            @click="emit('close')"
            class="px-3 py-1 bg-space-800 hover:bg-space-700 text-slate-300 rounded transition cursor-pointer"
          >
            Cerrar
          </button>
        </div>
      </div>
    </dialog>
  </Teleport>
</template>
