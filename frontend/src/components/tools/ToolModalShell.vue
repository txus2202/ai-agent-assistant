<script setup lang="ts">
import { computed, ref } from 'vue'
import { X } from '@lucide/vue'

const props = withDefaults(
  defineProps<{
    isOpen: boolean
    backdropTestId: string
    closeBtnTestId: string
    modalTitleId: string
    title: string
    accentTheme?: 'cyan' | 'pink'
    maxWidthClass?: string
    paddingClass?: string
    headerBgClass?: string
    selectNoneWindow?: boolean
    teleportDisabled?: boolean
  }>(),
  {
    accentTheme: 'cyan',
    maxWidthClass: 'max-w-6xl',
    paddingClass:
      'p-4 md:p-8 pt-[max(1rem,env(safe-area-inset-top))] pb-[max(1rem,env(safe-area-inset-bottom))]',
    headerBgClass: 'bg-[#080d1a]',
    selectNoneWindow: false,
    teleportDisabled: false,
  },
)

const emit = defineEmits<{
  (e: 'close'): void
}>()

const isTestEnv = import.meta !== undefined && import.meta.env?.MODE === 'test'
const shouldDisableTeleport = computed(() => props.teleportDisabled || isTestEnv)
const modalWindowRef = ref<HTMLElement | null>(null)

const windowClasses = computed(() =>
  props.accentTheme === 'pink'
    ? 'border-pink-500/40 shadow-[0_0_50px_rgba(236,72,153,0.15)]'
    : 'border-cyan-500/40 shadow-[0_0_50px_rgba(0,229,255,0.2)]',
)

const iconBoxClasses = computed(() =>
  props.accentTheme === 'pink'
    ? 'bg-pink-500/10 border-pink-500/40 text-pink-400 shadow-[0_0_10px_rgba(236,72,153,0.2)]'
    : 'bg-neon-cyan/10 border-neon-cyan/40 text-neon-cyan shadow-[0_0_10px_rgba(0,229,255,0.2)]',
)

const titleClasses = computed(() =>
  props.accentTheme === 'pink' ? 'text-pink-400' : 'text-neon-cyan',
)

defineExpose({
  windowElement: modalWindowRef,
})
</script>

<template>
  <Teleport to="body" :disabled="shouldDisableTeleport">
    <dialog
      v-if="isOpen"
      open
      :data-test="backdropTestId"
      class="fixed inset-0 z-[99999] bg-black/85 backdrop-blur-md flex flex-col items-center justify-center animate-fade-in border-0 m-0 w-full h-full max-w-none max-h-none text-inherit"
      :class="paddingClass"
      @click.self="emit('close')"
      @cancel.prevent="emit('close')"
      :aria-labelledby="modalTitleId"
      aria-modal="true"
    >
      <div
        ref="modalWindowRef"
        class="w-full h-[94vh] sm:h-[88vh] max-h-[100dvh] bg-[#060a11] border rounded-xl sm:rounded-2xl flex flex-col overflow-hidden m-auto"
        :class="[maxWidthClass, windowClasses, selectNoneWindow ? 'select-none' : '']"
      >
        <div
          class="flex items-center justify-between px-3 sm:px-6 py-2.5 sm:py-4 border-b border-space-800 gap-2 min-w-0"
          :class="headerBgClass"
        >
          <div class="flex items-center gap-2 sm:gap-2.5 shrink-0">
            <div
              class="w-7 h-7 sm:w-8 sm:h-8 rounded-lg border flex items-center justify-center shrink-0"
              :class="iconBoxClasses"
            >
              <slot name="icon" />
            </div>
            <h3
              :id="modalTitleId"
              class="text-xs sm:text-sm font-mono font-bold tracking-wider uppercase select-none"
              :class="titleClasses"
            >
              {{ title }}
            </h3>
          </div>

          <div class="flex items-center gap-1 sm:gap-2 shrink-0">
            <slot name="toolbar" />

            <button
              type="button"
              @click="emit('close')"
              :data-test="closeBtnTestId"
              class="relative group p-1.5 sm:p-2 rounded-lg bg-[#030509] border border-space-700 hover:border-red-500/50 hover:bg-red-950/30 text-slate-400 hover:text-red-400 transition-colors ml-0.5 sm:ml-1 cursor-pointer flex items-center justify-center shrink-0"
              title="Cerrar (Esc)"
              aria-label="Cerrar"
            >
              <X class="w-3.5 h-3.5 sm:w-4 sm:h-4" />
              <span
                class="pointer-events-none absolute top-full mt-2 right-0 whitespace-nowrap rounded bg-[#03060c] px-2 py-0.5 text-[10px] font-mono text-slate-300 border border-space-700 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50 select-none"
              >
                Cerrar (Esc)
              </span>
            </button>
          </div>
        </div>

        <slot />
      </div>
    </dialog>
  </Teleport>
</template>

