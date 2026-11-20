<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Shield, Users, X } from '@lucide/vue'
import { useModalShortcuts } from '../composables/useModalShortcuts'
import { useAuthStore, type User } from '../stores/auth'
import { useDebateStore } from '../stores/debate'
import UserCreateForm, { type CreateUserFormPayload } from './users/UserCreateForm.vue'
import UserListPanel from './users/UserListPanel.vue'

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
const authStore = useAuthStore()

const isTestEnv = import.meta !== undefined && import.meta.env?.MODE === 'test'
const shouldDisableTeleport = computed(() => props.teleportDisabled || isTestEnv)

const createFormRef = ref<InstanceType<typeof UserCreateForm> | null>(null)
const localError = ref<string | null>(null)
const successMessage = ref<string | null>(null)
const isSubmitting = ref(false)
const editingUserId = ref<string | null>(null)
const confirmDeleteUserId = ref<string | null>(null)

const resetFeedbackAndSelection = () => {
  localError.value = null
  successMessage.value = null
  editingUserId.value = null
  confirmDeleteUserId.value = null
  createFormRef.value?.resetFields()
}

const loadUsers = async () => {
  await authStore.fetchUsers()
}

watch(
  () => props.isOpen,
  async (newVal) => {
    if (newVal) {
      resetFeedbackAndSelection()
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

useModalShortcuts(() => props.isOpen, handleKeyDown)

const handleCreateUser = async (payload: CreateUserFormPayload) => {
  localError.value = null
  successMessage.value = null

  const cleanUsername = payload.username.trim()
  if (!cleanUsername) {
    localError.value = 'El nombre de usuario es obligatorio'
    return
  }

  if (payload.password.length < 8) {
    localError.value = 'La contraseña debe tener al menos 8 caracteres'
    return
  }

  if (payload.password !== payload.confirmPassword) {
    localError.value = 'Las contraseñas no coinciden'
    return
  }

  isSubmitting.value = true
  try {
    const created = await authStore.createUser(cleanUsername, payload.password, payload.isAdmin)
    if (created) {
      successMessage.value = `Operador creado correctamente: ${created.username}`
      createFormRef.value?.resetFields()
    } else {
      localError.value = authStore.errorMessage || 'No se pudo crear el operador'
    }
  } finally {
    isSubmitting.value = false
  }
}

const isSelf = (userId: string): boolean => authStore.user?.id === userId

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
  confirmDeleteUserId.value = null
  localError.value = null
  successMessage.value = null
}

const cancelEdit = () => {
  editingUserId.value = null
}

const saveEdit = async (user: User, editPayload: { isAdmin: boolean; password: string }) => {
  localError.value = null
  successMessage.value = null

  if (editPayload.password && editPayload.password.length < 8) {
    localError.value = 'La nueva contraseña debe tener al menos 8 caracteres'
    return
  }

  const payload: { is_admin?: boolean; password?: string } = {
    is_admin: editPayload.isAdmin,
  }
  if (editPayload.password) {
    payload.password = editPayload.password
  }

  const updated = await authStore.updateUser(user.id, payload)
  if (updated) {
    successMessage.value = `Operador ${updated.username} actualizado correctamente`
    editingUserId.value = null
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
</script>

<template>
  <Teleport to="body" :disabled="shouldDisableTeleport">
    <dialog
      v-if="isOpen"
      open
      data-test="user-management-modal-backdrop"
      class="fixed inset-0 z-[99999] bg-black/80 backdrop-blur-md flex flex-col items-center justify-center p-4 md:p-6 border-0 m-0 w-full h-full max-w-none max-h-none text-inherit"
      @click.self="emit('close')"
      @keydown.enter.self="emit('close')"
      @cancel.prevent="emit('close')"
      aria-labelledby="user-modal-title"
      aria-modal="true"
    >
      <div
        class="w-full max-w-5xl max-h-[92vh] bg-space-900 border border-cyan-500/40 rounded-xl shadow-[0_0_40px_rgba(0,229,255,0.15)] flex flex-col overflow-hidden m-auto"
      >
        <div class="flex items-center justify-between px-6 py-4 border-b border-space-800 bg-space-950/80">
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
                <span
                  class="text-[10px] px-2 py-0.5 rounded bg-cyan-950 border border-cyan-500/30 text-cyan-400 font-mono"
                >
                  ACCESO RESTRINGIDO
                </span>
              </h2>
              <p class="text-[11px] font-mono text-cyan-300/70 tracking-wide">
                Administración de credenciales, roles y ciclo de vida de operadores
                {{ debateStore.projectName }}.
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

        <div class="p-6 overflow-y-auto grid grid-cols-1 lg:grid-cols-12 gap-6 bg-space-900/60">
          <UserCreateForm
            ref="createFormRef"
            :local-error="localError"
            :success-message="successMessage"
            :is-submitting="isSubmitting"
            :is-store-loading="authStore.isLoading"
            @submit="handleCreateUser"
          />

          <UserListPanel
            :users="authStore.users"
            :current-user-id="authStore.user?.id"
            :users-loading="authStore.usersLoading"
            :is-store-loading="authStore.isLoading"
            :editing-user-id="editingUserId"
            :confirm-delete-user-id="confirmDeleteUserId"
            @refresh="loadUsers"
            @toggle-active="toggleUserActive"
            @start-edit="startEdit"
            @cancel-edit="cancelEdit"
            @save-edit="saveEdit"
            @prompt-delete="promptDelete"
            @cancel-delete="cancelDelete"
            @confirm-delete="confirmDelete"
          />
        </div>

        <div
          class="px-6 py-3 border-t border-space-800 bg-space-950/80 flex items-center justify-between text-[11px] font-mono text-slate-500"
        >
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
