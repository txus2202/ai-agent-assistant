<script setup lang="ts">
import { ref } from 'vue'
import { Edit2, KeyRound, Power, RefreshCw, Trash2 } from '@lucide/vue'
import type { User } from '../../stores/auth'

const props = defineProps<{
  users: User[]
  currentUserId?: string
  usersLoading: boolean
  isStoreLoading: boolean
  editingUserId: string | null
  confirmDeleteUserId: string | null
}>()

const emit = defineEmits<{
  (e: 'refresh'): void
  (e: 'toggle-active', user: User): void
  (e: 'start-edit', user: User): void
  (e: 'cancel-edit'): void
  (e: 'save-edit', user: User, payload: { isAdmin: boolean; password: string }): void
  (e: 'prompt-delete', userId: string): void
  (e: 'cancel-delete'): void
  (e: 'confirm-delete', userId: string): void
}>()

const editIsAdmin = ref(false)
const editPassword = ref('')

const isSelf = (userId: string): boolean => props.currentUserId === userId

const onStartEdit = (user: User) => {
  editIsAdmin.value = user.is_admin
  editPassword.value = ''
  emit('start-edit', user)
}

const onCancelEdit = () => {
  editPassword.value = ''
  emit('cancel-edit')
}

const onSaveEdit = (user: User) => {
  emit('save-edit', user, {
    isAdmin: editIsAdmin.value,
    password: editPassword.value,
  })
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
  <div class="lg:col-span-7 flex flex-col gap-3 bg-space-950/30 p-5 rounded-lg border border-cyan-900/20">
    <div class="flex items-center justify-between pb-2 border-b border-space-800">
      <div class="flex items-center gap-2">
        <KeyRound class="w-4 h-4 text-cyan-400" />
        <h3 class="text-xs font-mono font-bold uppercase tracking-wider text-cyan-200">
          Operadores Registrados ({{ users.length }})
        </h3>
      </div>
      <button
        type="button"
        @click="emit('refresh')"
        :disabled="usersLoading"
        class="flex items-center gap-1 text-[11px] font-mono text-slate-400 hover:text-cyan-300 transition-colors cursor-pointer"
        title="Actualizar lista"
      >
        <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': usersLoading }" />
        <span>Refrescar</span>
      </button>
    </div>

    <div v-if="usersLoading" class="py-8 text-center text-xs font-mono text-cyan-400/80">
      Cargando operadores del sistema...
    </div>

    <div v-else-if="users.length === 0" class="py-8 text-center text-xs font-mono text-slate-500">
      No hay operadores registrados.
    </div>

    <div v-else class="space-y-3 max-h-[460px] overflow-y-auto pr-1">
      <div
        v-for="user in users"
        :key="user.id"
        data-test="user-item"
        class="p-3 rounded bg-space-900/80 border border-space-800 hover:border-cyan-800/40 flex flex-col gap-2 transition-colors"
      >
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3 min-w-0">
            <div
              class="w-7 h-7 rounded-full flex items-center justify-center font-mono text-xs font-bold shrink-0"
              :class="
                user.is_admin
                  ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                  : 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
              "
            >
              {{ user.username.charAt(0).toUpperCase() }}
            </div>
            <div class="truncate">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="text-xs font-mono font-bold text-cyan-100">{{ user.username }}</span>
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

          <div class="flex items-center gap-1.5 shrink-0">
            <button
              type="button"
              @click="emit('toggle-active', user)"
              data-test="toggle-active-btn"
              :disabled="isSelf(user.id) || isStoreLoading"
              class="px-2 py-0.5 rounded text-[10px] font-mono flex items-center gap-1 transition cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed border"
              :class="
                user.is_active
                  ? 'bg-emerald-950/40 text-emerald-300 border-emerald-500/40 hover:bg-emerald-900/60'
                  : 'bg-red-950/40 text-red-300 border-red-500/40 hover:bg-red-900/60'
              "
              :title="
                isSelf(user.id)
                  ? 'No puedes desactivar tu propia cuenta'
                  : user.is_active
                    ? 'Desactivar operador'
                    : 'Activar operador'
              "
            >
              <Power class="w-3 h-3" />
              <span>{{ user.is_active ? 'ACTIVO' : 'INACTIVO' }}</span>
            </button>

            <button
              type="button"
              @click="onStartEdit(user)"
              data-test="edit-user-btn"
              class="p-1 rounded text-slate-400 hover:text-cyan-300 hover:bg-space-800 transition cursor-pointer"
              title="Modificar operador"
            >
              <Edit2 class="w-3.5 h-3.5" />
            </button>

            <button
              type="button"
              @click="emit('prompt-delete', user.id)"
              data-test="delete-user-btn"
              :disabled="isSelf(user.id) || isStoreLoading"
              class="p-1 rounded text-slate-400 hover:text-red-400 hover:bg-space-800 transition cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
              :title="isSelf(user.id) ? 'No puedes eliminar tu propia cuenta' : 'Eliminar operador'"
            >
              <Trash2 class="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

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
              @click="onCancelEdit"
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
                <span class="text-xs font-mono text-slate-300">Rol Administrador</span>
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
              @click="onCancelEdit"
              class="px-2.5 py-1 text-[11px] font-mono text-slate-400 hover:text-slate-200 cursor-pointer"
            >
              Descartar
            </button>
            <button
              type="button"
              @click="onSaveEdit(user)"
              data-test="save-edit-btn"
              :disabled="isStoreLoading"
              class="px-3 py-1 bg-cyan-600 hover:bg-cyan-500 text-space-950 font-mono font-bold text-xs rounded transition cursor-pointer"
            >
              Guardar Cambios
            </button>
          </div>
        </div>

        <div
          v-if="confirmDeleteUserId === user.id"
          data-test="confirm-delete-box"
          class="mt-2 p-3 rounded bg-red-950/40 border border-red-500/50 space-y-2 animate-fade-in"
        >
          <div class="text-xs font-mono text-red-200">
            ¿Estás seguro de que deseas eliminar al operador
            <span class="font-bold underline">{{ user.username }}</span>?
          </div>
          <div class="text-[10px] font-mono text-slate-400">
            La estrategia configurada se aplicará de acuerdo a la variable del entorno (soft-delete
            / hard-delete).
          </div>
          <div class="flex justify-end gap-2 pt-1">
            <button
              type="button"
              @click="emit('cancel-delete')"
              class="px-2.5 py-1 text-[11px] font-mono text-slate-400 hover:text-slate-200 cursor-pointer"
            >
              Cancelar
            </button>
            <button
              type="button"
              @click="emit('confirm-delete', user.id)"
              data-test="confirm-delete-btn"
              :disabled="isStoreLoading"
              class="px-3 py-1 bg-red-600 hover:bg-red-500 text-white font-mono font-bold text-xs rounded transition cursor-pointer"
            >
              Confirmar Eliminación
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

