import { watch, onMounted, onUnmounted, getCurrentInstance, type Ref } from 'vue'

export interface TouchSwipeOptions {
  onSwipeUp?: () => void
  onSwipeDown?: () => void
  onSwipeLeft?: () => void
  onSwipeRight?: () => void
  threshold?: number
  ignoreInteractive?: boolean
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
  const ignoreInteractive = options.ignoreInteractive ?? true

  let touchStartY = 0
  let touchStartX = 0
  let touchCurrentY = 0
  let touchCurrentX = 0
  let isTrackingTouch = false
  let lastTouchEndTime = 0
  let suppressNextPointerClick = false

  const triggerSwipeIfExceeded = (deltaY: number, deltaX: number): boolean => {
    const absY = Math.abs(deltaY)
    const absX = Math.abs(deltaX)
    if (absY >= threshold && absY > absX * 1.1) {
      if (deltaY < 0) {
        options.onSwipeUp?.()
      } else {
        options.onSwipeDown?.()
      }
      return true
    } else if (absX >= threshold && absX > absY * 1.1) {
      if (deltaX < 0) {
        options.onSwipeLeft?.()
      } else {
        options.onSwipeRight?.()
      }
      return true
    }
    return false
  }

  const isInteractive = (target: EventTarget | null): boolean => {
    const el = target as HTMLElement | null
    if (!ignoreInteractive) {
      // Allow dragging on collapsible handle bars, but still ignore actual form inputs or inner action buttons like #micButton
      return Boolean(
        el?.closest?.(
          '#micButton, [data-test="soundbar-view-switch"], [data-test="hitl-retry-btn"], [data-test="hitl-target-chip"], [data-test="hitl-approve-btn"], [data-test="hitl-consolidate-btn"], [data-test="hitl-finish-btn"], [data-test="hitl-refine-btn"], [data-test="hitl-divert-btn"], [data-test="hitl-reject-btn"], a, input, textarea, select',
        ),
      )
    }
    return Boolean(el?.closest?.('button, a, input, textarea, select, [role="button"]'))
  }

  const handleClickCapture = (e: MouseEvent) => {
    if (suppressNextPointerClick) {
      suppressNextPointerClick = false
      e.preventDefault()
      e.stopPropagation()
    }
  }

  const handleTouchStart = (e: TouchEvent) => {
    suppressNextPointerClick = false
    if (isInteractive(e.target)) return
    const list = e.touches?.length ? e.touches : e.changedTouches
    if (list?.length !== 1) return
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
    lastTouchEndTime = Date.now()
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
    lastTouchEndTime = Date.now()
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
    suppressNextPointerClick = false
    if (isInteractive(e.target)) return
    // If touch was recently active, ignore synthetic pointer events to avoid double-triggers
    if (Date.now() - lastTouchEndTime < 500) return
    if (isTrackingTouch) return
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
    if (triggerSwipeIfExceeded(deltaY, deltaX)) {
      suppressNextPointerClick = true
    }
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
  element.addEventListener('click', handleClickCapture, true)

  return () => {
    element.removeEventListener('touchstart', handleTouchStart)
    element.removeEventListener('touchmove', handleTouchMove)
    element.removeEventListener('touchend', handleTouchEnd)
    element.removeEventListener('touchcancel', handleTouchCancel)
    element.removeEventListener('pointerdown', handlePointerDown)
    element.removeEventListener('pointermove', handlePointerMove)
    element.removeEventListener('pointerup', handlePointerUp)
    element.removeEventListener('pointercancel', handlePointerCancel)
    element.removeEventListener('click', handleClickCapture, true)
  }
}

/**
 * Vue Composable for touch/pointer swipe gestures.
 * Watches elementRef dynamically so elements mounted via v-if or teleport
 * attach listeners reliably.
 */
export function useTouchSwipe(
  elementRef: Ref<HTMLElement | null>,
  options: TouchSwipeOptions
) {
  let cleanup: (() => void) | null = null

  const attach = (el: HTMLElement | null) => {
    if (cleanup) {
      cleanup()
      cleanup = null
    }
    if (el) {
      cleanup = setupSwipeListener(el, options)
    }
  }

  watch(
    elementRef,
    (newEl) => {
      attach(newEl)
    },
    { immediate: true, flush: 'post' }
  )

  if (getCurrentInstance()) {
    onMounted(() => {
      if (elementRef.value && !cleanup) {
        attach(elementRef.value)
      }
    })

    onUnmounted(() => {
      if (cleanup) {
        cleanup()
        cleanup = null
      }
    })
  }
}

