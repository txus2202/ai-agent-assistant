import { describe, it, expect, vi } from 'vitest'
import { ref, nextTick } from 'vue'
import { setupSwipeListener, useTouchSwipe } from '../touchSwipe'

describe('touchSwipe utility', () => {
  it('triggers onSwipeUp on upward touch gesture', () => {
    const el = document.createElement('div')
    const onSwipeUp = vi.fn()
    const onSwipeDown = vi.fn()

    const cleanup = setupSwipeListener(el, {
      onSwipeUp,
      onSwipeDown,
      threshold: 30,
    })

    // Simulate touchstart at y=200
    const startEvent = new TouchEvent('touchstart', {
      touches: [{ clientX: 100, clientY: 200 } as unknown as Touch],
    })
    el.dispatchEvent(startEvent)

    // Simulate touchend at y=150 (deltaY = -50 -> swipe UP)
    const endEvent = new TouchEvent('touchend', {
      changedTouches: [{ clientX: 100, clientY: 150 } as unknown as Touch],
    })
    el.dispatchEvent(endEvent)

    expect(onSwipeUp).toHaveBeenCalledTimes(1)
    expect(onSwipeDown).not.toHaveBeenCalled()

    cleanup()
  })

  it('triggers onSwipeDown on downward touch gesture', () => {
    const el = document.createElement('div')
    const onSwipeUp = vi.fn()
    const onSwipeDown = vi.fn()

    const cleanup = setupSwipeListener(el, {
      onSwipeUp,
      onSwipeDown,
      threshold: 30,
    })

    // Simulate touchstart at y=100
    const startEvent = new TouchEvent('touchstart', {
      touches: [{ clientX: 100, clientY: 100 } as unknown as Touch],
    })
    el.dispatchEvent(startEvent)

    // Simulate touchend at y=160 (deltaY = +60 -> swipe DOWN)
    const endEvent = new TouchEvent('touchend', {
      changedTouches: [{ clientX: 100, clientY: 160 } as unknown as Touch],
    })
    el.dispatchEvent(endEvent)

    expect(onSwipeDown).toHaveBeenCalledTimes(1)
    expect(onSwipeUp).not.toHaveBeenCalled()

    cleanup()
  })

  it('ignores swipes below threshold', () => {
    const el = document.createElement('div')
    const onSwipeUp = vi.fn()
    const onSwipeDown = vi.fn()

    const cleanup = setupSwipeListener(el, {
      onSwipeUp,
      onSwipeDown,
      threshold: 30,
    })

    const startEvent = new TouchEvent('touchstart', {
      touches: [{ clientX: 100, clientY: 100 } as unknown as Touch],
    })
    el.dispatchEvent(startEvent)

    // Delta is only 15px (< 30px)
    const endEvent = new TouchEvent('touchend', {
      changedTouches: [{ clientX: 100, clientY: 85 } as unknown as Touch],
    })
    el.dispatchEvent(endEvent)

    expect(onSwipeUp).not.toHaveBeenCalled()
    expect(onSwipeDown).not.toHaveBeenCalled()

    cleanup()
  })

  it('triggers onSwipeLeft on leftward touch gesture', () => {
    const el = document.createElement('div')
    const onSwipeLeft = vi.fn()
    const onSwipeRight = vi.fn()
    const onSwipeUp = vi.fn()

    const cleanup = setupSwipeListener(el, {
      onSwipeLeft,
      onSwipeRight,
      onSwipeUp,
      threshold: 30,
    })

    const startEvent = new TouchEvent('touchstart', {
      touches: [{ clientX: 200, clientY: 100 } as unknown as Touch],
    })
    el.dispatchEvent(startEvent)

    // Move left: clientX from 200 to 140 (deltaX = -60, deltaY = 5)
    const endEvent = new TouchEvent('touchend', {
      changedTouches: [{ clientX: 140, clientY: 105 } as unknown as Touch],
    })
    el.dispatchEvent(endEvent)

    expect(onSwipeLeft).toHaveBeenCalledTimes(1)
    expect(onSwipeRight).not.toHaveBeenCalled()
    expect(onSwipeUp).not.toHaveBeenCalled()

    cleanup()
  })

  it('triggers onSwipeRight on rightward touch gesture', () => {
    const el = document.createElement('div')
    const onSwipeLeft = vi.fn()
    const onSwipeRight = vi.fn()
    const onSwipeDown = vi.fn()

    const cleanup = setupSwipeListener(el, {
      onSwipeLeft,
      onSwipeRight,
      onSwipeDown,
      threshold: 30,
    })

    const startEvent = new TouchEvent('touchstart', {
      touches: [{ clientX: 100, clientY: 100 } as unknown as Touch],
    })
    el.dispatchEvent(startEvent)

    // Move right: clientX from 100 to 170 (deltaX = +70, deltaY = -5)
    const endEvent = new TouchEvent('touchend', {
      changedTouches: [{ clientX: 170, clientY: 95 } as unknown as Touch],
    })
    el.dispatchEvent(endEvent)

    expect(onSwipeRight).toHaveBeenCalledTimes(1)
    expect(onSwipeLeft).not.toHaveBeenCalled()
    expect(onSwipeDown).not.toHaveBeenCalled()

    cleanup()
  })

  it('triggers onSwipeLeft on pointer event swipe left', () => {
    const el = document.createElement('div')
    const onSwipeLeft = vi.fn()

    const cleanup = setupSwipeListener(el, {
      onSwipeLeft,
      threshold: 30,
    })

    const pDown = new PointerEvent('pointerdown', {
      clientX: 200,
      clientY: 100,
      pointerType: 'touch',
    })
    el.dispatchEvent(pDown)

    const pUp = new PointerEvent('pointerup', {
      clientX: 120,
      clientY: 100,
      pointerType: 'touch',
    })
    el.dispatchEvent(pUp)

    expect(onSwipeLeft).toHaveBeenCalledTimes(1)
    cleanup()
  })

  it('triggers on pointer events when using pointerdown/pointerup', () => {
    const el = document.createElement('div')
    const onSwipeUp = vi.fn()
    const onSwipeDown = vi.fn()

    const cleanup = setupSwipeListener(el, {
      onSwipeUp,
      onSwipeDown,
      threshold: 30,
    })

    // Pointer down
    const pDown = new PointerEvent('pointerdown', {
      clientX: 50,
      clientY: 200,
      pointerType: 'touch',
    })
    el.dispatchEvent(pDown)

    // Pointer up at clientY = 120 (delta = -80 -> UP)
    const pUp = new PointerEvent('pointerup', {
      clientX: 50,
      clientY: 120,
      pointerType: 'touch',
    })
    el.dispatchEvent(pUp)

    expect(onSwipeUp).toHaveBeenCalledTimes(1)
    cleanup()
  })

  it('useTouchSwipe attaches listener when elementRef changes from null to element', async () => {
    const elRef = ref<HTMLElement | null>(null)
    const onSwipeLeft = vi.fn()
    useTouchSwipe(elRef, { onSwipeLeft, threshold: 30 })

    const el = document.createElement('div')
    elRef.value = el
    await nextTick()

    // Dispatch touch gesture on el
    const startEvent = new TouchEvent('touchstart', {
      touches: [{ clientX: 200, clientY: 100 } as unknown as Touch],
    })
    el.dispatchEvent(startEvent)

    const endEvent = new TouchEvent('touchend', {
      changedTouches: [{ clientX: 140, clientY: 105 } as unknown as Touch],
    })
    el.dispatchEvent(endEvent)

    expect(onSwipeLeft).toHaveBeenCalledTimes(1)
  })
})
