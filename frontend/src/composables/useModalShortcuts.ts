import { onUnmounted, watch, type WatchSource } from 'vue'

/**
 * Registers a `window` `keydown` handler only while a modal is open and removes
 * it automatically on close or unmount so keystrokes never leak or fire twice.
 */
export function useModalShortcuts(
  isOpen: WatchSource<boolean>,
  onKeyDown: (event: KeyboardEvent) => void,
): void {
  let isListening = false

  const attach = () => {
    if (isListening || typeof window === 'undefined') return
    window.addEventListener('keydown', onKeyDown)
    isListening = true
  }

  const detach = () => {
    if (!isListening || typeof window === 'undefined') return
    window.removeEventListener('keydown', onKeyDown)
    isListening = false
  }

  watch(
    isOpen,
    (open) => {
      if (open) {
        attach()
      } else {
        detach()
      }
    },
    { immediate: true },
  )

  onUnmounted(() => {
    detach()
  })
}

