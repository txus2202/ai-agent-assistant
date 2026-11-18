import { onUnmounted, ref, type Ref } from 'vue'

/**
 * Manages a temporary reactive value (such as a "copied" badge state) that
 * resets to `initialValue` after `delayMs`, cancelling prior timers and
 * cleaning up deterministically on component unmount.
 */
export function useTimedReset<T>(initialValue: T, delayMs = 2000): {
  state: Ref<T>
  trigger: (activeValue: T) => void
  clear: () => void
} {
  const state = ref(initialValue) as Ref<T>
  let timerId: ReturnType<typeof setTimeout> | null = null

  const clear = () => {
    if (timerId !== null) {
      clearTimeout(timerId)
      timerId = null
    }
  }

  const trigger = (activeValue: T) => {
    clear()
    state.value = activeValue
    timerId = setTimeout(() => {
      timerId = null
      if (state.value === activeValue) {
        state.value = initialValue
      }
    }, delayMs)
  }

  onUnmounted(() => {
    clear()
  })

  return { state, trigger, clear }
}

