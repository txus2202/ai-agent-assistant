import { onMounted, onUnmounted, type Ref } from 'vue'

export interface TouchSwipeOptions {
  onSwipeUp?: () => void
  onSwipeDown?: () => void
  threshold?: number
}

/**
 * Attaches touch and pointer swipe listeners to an HTMLElement.
 * Returns a cleanup function.
 * Zero external dependencies.
 */
export function setupSwipeListener(
  element: HTMLElement,
  options: TouchSwipeOptions
): () => void {
  const threshold = options.threshold ?? 25

  let touchStartY = 0
  let touchStartX = 0
  let touchCurrentY = 0
  let touchCurrentX = 0
  let isTrackingTouch = false

  const triggerSwipeIfExceeded = (deltaY: number, deltaX: number) => {
    if (Math.abs(deltaY) >= threshold && Math.abs(deltaY) > Math.abs(deltaX) * 1.1) {
      if (deltaY < 0) {
        options.onSwipeUp?.()
      } else {
        options.onSwipeDown?.()
      }
    }
  }

  const handleTouchStart = (e: TouchEvent) => {
    const list = (e.touches && e.touches.length > 0) ? e.touches : e.changedTouches
    if (!list || list.length !== 1) return
    const touch = list[0]
    if (!touch) return
    touchStartY = touch.clientY
    touchStartX = touch.clientX
    touchCurrentY = touch.clientY
    touchCurrentX = touch.clientX
    isTrackingTouch = true
  }

  const handleTouchMove = (e: TouchEvent) => {
    if (!isTrackingTouch) return
    const touch = e.touches[0] || e.changedTouches[0]
    if (!touch) return
    touchCurrentY = touch.clientY
    touchCurrentX = touch.clientX
  }

  const handleTouchEnd = (e: TouchEvent) => {
    if (!isTrackingTouch) return
    isTrackingTouch = false
    const touch = e.changedTouches[0] || e.touches[0]
    const endY = touch ? touch.clientY : touchCurrentY
    const endX = touch ? touch.clientX : touchCurrentX
    const deltaY = endY - touchStartY
    const deltaX = endX - touchStartX
    triggerSwipeIfExceeded(deltaY, deltaX)
  }

  const handleTouchCancel = () => {
    if (!isTrackingTouch) return
    isTrackingTouch = false
    const deltaY = touchCurrentY - touchStartY
    const deltaX = touchCurrentX - touchStartX
    triggerSwipeIfExceeded(deltaY, deltaX)
  }

  let pointerStartY = 0
  let pointerStartX = 0
  let pointerCurrentY = 0
  let pointerCurrentX = 0
  let isTrackingPointer = false

  const handlePointerDown = (e: PointerEvent) => {
    if (e.pointerType === 'mouse' && e.button !== 0) return
    pointerStartY = e.clientY
    pointerStartX = e.clientX
    pointerCurrentY = e.clientY
    pointerCurrentX = e.clientX
    isTrackingPointer = true
  }

  const handlePointerMove = (e: PointerEvent) => {
    if (!isTrackingPointer) return
    pointerCurrentY = e.clientY
    pointerCurrentX = e.clientX
  }

  const handlePointerUp = (e: PointerEvent) => {
    if (!isTrackingPointer) return
    isTrackingPointer = false
    const deltaY = e.clientY - pointerStartY
    const deltaX = e.clientX - pointerStartX
    triggerSwipeIfExceeded(deltaY, deltaX)
  }

  const handlePointerCancel = () => {
    if (!isTrackingPointer) return
    isTrackingPointer = false
    const deltaY = pointerCurrentY - pointerStartY
    const deltaX = pointerCurrentX - pointerStartX
    triggerSwipeIfExceeded(deltaY, deltaX)
  }

  element.addEventListener('touchstart', handleTouchStart, { passive: true })
  element.addEventListener('touchmove', handleTouchMove, { passive: true })
  element.addEventListener('touchend', handleTouchEnd, { passive: true })
  element.addEventListener('touchcancel', handleTouchCancel, { passive: true })
  element.addEventListener('pointerdown', handlePointerDown)
  element.addEventListener('pointermove', handlePointerMove)
  element.addEventListener('pointerup', handlePointerUp)
  element.addEventListener('pointercancel', handlePointerCancel)

  return () => {
    element.removeEventListener('touchstart', handleTouchStart)
    element.removeEventListener('touchmove', handleTouchMove)
    element.removeEventListener('touchend', handleTouchEnd)
    element.removeEventListener('touchcancel', handleTouchCancel)
    element.removeEventListener('pointerdown', handlePointerDown)
    element.removeEventListener('pointermove', handlePointerMove)
    element.removeEventListener('pointerup', handlePointerUp)
    element.removeEventListener('pointercancel', handlePointerCancel)
  }
}

/**
 * Vue Composable for touch/pointer swipe gestures.
 * Zero external dependencies.
 */
export function useTouchSwipe(
  elementRef: Ref<HTMLElement | null>,
  options: TouchSwipeOptions
) {
  let cleanup: (() => void) | null = null

  onMounted(() => {
    if (elementRef.value) {
      cleanup = setupSwipeListener(elementRef.value, options)
    }
  })

  onUnmounted(() => {
    if (cleanup) {
      cleanup()
      cleanup = null
    }
  })
}

