<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  decision: 'approve' | 'refine' | 'reject'
  disabled?: boolean
}>()

const emit = defineEmits<{
  (e: 'action', decision: 'approve' | 'refine' | 'reject'): void
}>()

const buttonText = computed(() => {
  switch (props.decision) {
    case 'approve': return 'APPROVE / MERGE'
    case 'refine': return 'REFINE / ITERATE'
    case 'reject': return 'REJECT / ABORT'
    default: return 'ACTION'
  }
})

const buttonClass = computed(() => {
  switch (props.decision) {
    case 'approve': return 'border-neon-lightgreen text-neon-lightgreen hover:bg-neon-lightgreen/10'
    case 'refine': return 'border-neon-amber text-neon-amber hover:bg-neon-amber/10'
    case 'reject': return 'border-neon-red text-neon-red hover:bg-neon-red/10'
    default: return 'border-space-700 text-slate-300'
  }
})
</script>

<template>
  <button
    :disabled="disabled"
    @click="emit('action', decision)"
    class="px-4 py-2 border font-mono text-sm tracking-wider rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
    :class="buttonClass"
  >
    {{ buttonText }}
  </button>
</template>
