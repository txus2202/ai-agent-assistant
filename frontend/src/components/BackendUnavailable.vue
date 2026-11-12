<script setup lang="ts">
import { useDebateStore } from '../stores/debate'
import { useAuthStore } from '../stores/auth'
import { ServerOff, RefreshCw, AlertTriangle, ShieldAlert } from '@lucide/vue'

defineProps<{
  isRetrying?: boolean
}>()

const emit = defineEmits<{
  (e: 'retry'): void
}>()

const debateStore = useDebateStore()
const authStore = useAuthStore()

const handleRetry = () => {
  emit('retry')
}
</script>

<template>
  <div class="min-h-screen w-full bg-space-950 flex flex-col items-center justify-center p-4 relative overflow-hidden">
    <!-- Ambient glowing backgrounds in red/amber -->
    <div class="absolute -top-40 -left-40 w-96 h-96 bg-red-600/10 rounded-full blur-3xl pointer-events-none"></div>
    <div class="absolute -bottom-40 -right-40 w-96 h-96 bg-amber-600/10 rounded-full blur-3xl pointer-events-none"></div>

    <div class="w-full max-w-lg relative z-10">
      <!-- Header branding -->
      <div class="text-center mb-6">
        <div class="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-space-900 border border-red-500/40 shadow-[0_0_30px_rgba(239,68,68,0.2)] mb-3">
          <ServerOff class="w-8 h-8 text-red-400 animate-pulse" />
        </div>
        <h1 class="text-xl sm:text-2xl font-bold tracking-widest uppercase font-mono text-cyan-100">
          {{ debateStore.projectName }}
        </h1>
        <p class="text-xs font-mono text-red-400/80 tracking-wider mt-1 uppercase flex items-center justify-center gap-1.5">
          <AlertTriangle class="w-3.5 h-3.5 text-red-400" />
          Servidor Backend No Disponible
        </p>
      </div>

      <!-- Error Card -->
      <div class="bg-space-900/90 border border-red-500/30 rounded-xl p-6 sm:p-8 backdrop-blur-xl shadow-[0_10px_35px_rgba(0,0,0,0.6)]">
        <div class="border-b border-space-800 pb-4 mb-5 flex items-center justify-between">
          <span class="text-xs font-mono font-bold uppercase tracking-wider text-red-400 flex items-center gap-2">
            <ShieldAlert class="w-4 h-4" />
            Error de Conexión
          </span>
          <span class="text-[10px] font-mono text-red-400 border border-red-500/40 px-2 py-0.5 rounded flex items-center gap-1.5">
            <span class="w-1.5 h-1.5 rounded-full bg-red-500 animate-ping"></span>
            SYS: OFFLINE
          </span>
        </div>

        <div class="space-y-4">
          <p class="text-xs font-mono text-slate-300 leading-relaxed">
            No se ha podido establecer comunicación con el núcleo del backend. El servidor puede estar apagado, en proceso de inicio o inaccesible en la red local.
          </p>

          <!-- Error details box -->
          <div class="p-3 rounded-lg bg-red-950/40 border border-red-500/30 text-red-200 text-xs font-mono">
            <div class="text-[10px] uppercase text-red-400/70 tracking-wider mb-1">Diagnóstico del sistema</div>
            <div class="text-red-300 font-semibold">{{ authStore.errorMessage || 'No se puede conectar con el servidor backend (puerto 8000).' }}</div>
          </div>

          <div class="text-[11px] font-mono text-slate-400 leading-relaxed">
            Por favor, inicie el servicio backend o espere a que complete su arranque y pulse el botón de reintentar.
          </div>

          <div class="pt-2">
            <button
              type="button"
              :disabled="isRetrying"
              @click="handleRetry"
              class="w-full py-2.5 px-4 bg-red-500/20 hover:bg-red-500/30 border border-red-500/50 hover:border-red-400 text-red-100 font-mono text-xs uppercase tracking-widest font-semibold rounded-lg transition-all duration-200 flex items-center justify-center gap-2 cursor-pointer shadow-[0_0_15px_rgba(239,68,68,0.2)] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <RefreshCw class="w-4 h-4 text-red-300" :class="{ 'animate-spin': isRetrying }" />
              <span v-if="!isRetrying">Reintentar Conexión</span>
              <span v-else>Comprobando Servidor...</span>
            </button>
          </div>
        </div>
      </div>

      <!-- Footer Info -->
      <div class="mt-6 text-center text-[11px] font-mono text-slate-600 uppercase tracking-widest">
        Acceso suspendido temporalmente &bull; {{ debateStore.projectName }} Core
      </div>
    </div>
  </div>
</template>

