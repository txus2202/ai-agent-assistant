import { describe, it, expect, vi } from 'vitest'
import { setupSwipeListener } from '../touchSwipe'

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

  it('ignores horizontal swipes', () => {
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

    // DeltaX = 80px, DeltaY = -35px (mostly horizontal)
    const endEvent = new TouchEvent('touchend', {
      changedTouches: [{ clientX: 180, clientY: 65 } as unknown as Touch],
    })
    el.dispatchEvent(endEvent)

    expect(onSwipeUp).not.toHaveBeenCalled()
    expect(onSwipeDown).not.toHaveBeenCalled()

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
})

