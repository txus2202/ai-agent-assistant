import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, enableAutoUnmount } from '@vue/test-utils'

enableAutoUnmount(afterEach)
import PresentationModal from '../PresentationModal.vue'
import * as exporter from '../../../utils/presentationExporter'

vi.mock('../../../utils/presentationExporter', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../utils/presentationExporter')>()
  return {
    ...actual,
    exportPresentationPptx: vi.fn().mockResolvedValue(undefined),
    downloadPresentationHtml: vi.fn(),
  }
})

describe('PresentationModal.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined)
      }
    })
  })

  const sampleMarkdown = `
# Arquitectura Atenea
---
## Resumen Ejecutivo
<!-- layout: hero -->
> Plataforma unificada de gestión de sesiones.
- **Decisión:** Opción Hestia-1
- **Objetivo:** Consistencia estricta
---
## Stack Tecnológico
<!-- layout: cards -->
### PostgreSQL
- Base de datos primaria
### Redis
- Caché de sesiones
---
## Métricas
- SLA 99.99%
`

  it('does not render when isOpen is false', () => {
    const wrapper = mount(PresentationModal, {
      props: {
        isOpen: false,
        content: sampleMarkdown,
        teleportDisabled: true
      }
    })
    expect(wrapper.find('[data-test="presentation-modal-backdrop"]').exists()).toBe(false)
  })

  it('renders modal with header and first slide when isOpen is true', () => {
    const wrapper = mount(PresentationModal, {
      props: {
        isOpen: true,
        content: sampleMarkdown,
        title: 'Arquitectura Atenea',
        teleportDisabled: true
      }
    })

    expect(wrapper.find('[data-test="presentation-modal-backdrop"]').exists()).toBe(true)
    expect(wrapper.find('#presentation-modal-title').text()).toBe('Presentación')
    expect(wrapper.text()).toContain('Resumen Ejecutivo')
    expect(wrapper.find('[data-test="slide-counter"]').text()).toContain('1 / 3')
  })

  it('navigates through slides with next and previous buttons', async () => {
    const wrapper = mount(PresentationModal, {
      props: {
        isOpen: true,
        content: sampleMarkdown,
        teleportDisabled: true
      }
    })

    expect(wrapper.find('[data-test="slide-counter"]').text()).toContain('1 / 3')
    expect(wrapper.text()).toContain('Resumen Ejecutivo')

    // Click Next
    await wrapper.find('[data-test="slide-next-btn"]').trigger('click')
    expect(wrapper.find('[data-test="slide-counter"]').text()).toContain('2 / 3')
    expect(wrapper.text()).toContain('Stack Tecnológico')
    expect(wrapper.text()).toContain('PostgreSQL')
    expect(wrapper.text()).toContain('Redis')

    // Click Next again to slide 3
    await wrapper.find('[data-test="slide-next-btn"]').trigger('click')
    expect(wrapper.find('[data-test="slide-counter"]').text()).toContain('3 / 3')
    expect(wrapper.text()).toContain('Métricas')

    // Click Next on last slide (should not advance)
    await wrapper.find('[data-test="slide-next-btn"]').trigger('click')
    expect(wrapper.find('[data-test="slide-counter"]').text()).toContain('3 / 3')

    // Click Prev to return to slide 2
    await wrapper.find('[data-test="slide-prev-btn"]').trigger('click')
    expect(wrapper.find('[data-test="slide-counter"]').text()).toContain('2 / 3')
  })

  it('navigates with keyboard arrow keys', async () => {
    const wrapper = mount(PresentationModal, {
      props: {
        isOpen: true,
        content: sampleMarkdown,
        teleportDisabled: true
      }
    })

    expect(wrapper.find('[data-test="slide-counter"]').text()).toContain('1 / 3')

    // Press ArrowRight
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight' }))
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-test="slide-counter"]').text()).toContain('2 / 3')

    // Press ArrowLeft
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowLeft' }))
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-test="slide-counter"]').text()).toContain('1 / 3')
  })

  it('copies presentation content on copy button click', async () => {
    const wrapper = mount(PresentationModal, {
      props: {
        isOpen: true,
        content: sampleMarkdown,
        teleportDisabled: true
      }
    })

    const copyBtn = wrapper.find('[data-test="presentation-modal-copy-btn"]')
    await copyBtn.trigger('click')

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(sampleMarkdown)
    expect(copyBtn.text()).toContain('Copiado')
  })

  it('emits close on close button click and escape key', async () => {
    const wrapper = mount(PresentationModal, {
      props: {
        isOpen: true,
        content: sampleMarkdown,
        teleportDisabled: true
      }
    })

    await wrapper.find('[data-test="presentation-modal-close-btn"]').trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)

    // Escape key
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(wrapper.emitted('close')).toHaveLength(2)
  })

  it('opens download dropdown and triggers exportPresentationPptx when selecting PPTX option', async () => {
    const wrapper = mount(PresentationModal, {
      props: {
        isOpen: true,
        content: sampleMarkdown,
        title: 'Arquitectura Atenea',
        teleportDisabled: true
      }
    })

    const downloadBtn = wrapper.find('[data-test="presentation-modal-download-btn"]')
    expect(downloadBtn.exists()).toBe(true)
    expect(wrapper.find('[data-test="presentation-download-dropdown"]').exists()).toBe(false)

    // Open dropdown
    await downloadBtn.trigger('click')
    expect(wrapper.find('[data-test="presentation-download-dropdown"]').exists()).toBe(true)

    // Click PPTX option
    const pptxOption = wrapper.find('[data-test="download-option-pptx"]')
    expect(pptxOption.exists()).toBe(true)
    await pptxOption.trigger('click')

    expect(exporter.exportPresentationPptx).toHaveBeenCalledTimes(1)
    // Dropdown closes after selection
    expect(wrapper.find('[data-test="presentation-download-dropdown"]').exists()).toBe(false)
  })

  it('triggers downloadPresentationHtml when selecting HTML option from dropdown', async () => {
    const wrapper = mount(PresentationModal, {
      props: {
        isOpen: true,
        content: sampleMarkdown,
        title: 'Arquitectura Atenea',
        teleportDisabled: true
      }
    })

    // Open dropdown
    await wrapper.find('[data-test="presentation-modal-download-btn"]').trigger('click')
    await wrapper.find('[data-test="download-option-html"]').trigger('click')

    expect(exporter.downloadPresentationHtml).toHaveBeenCalledTimes(1)
  })

  it('navigates slides on touch swipe left and swipe right', async () => {
    const wrapper = mount(PresentationModal, {
      props: {
        isOpen: true,
        content: sampleMarkdown,
        teleportDisabled: true
      }
    })

    const canvasEl = wrapper.find('[data-test="presentation-slide-canvas"]')

    expect(wrapper.find('[data-test="slide-counter"]').text()).toContain('1 / 3')

    // Swipe left (advance to next slide)
    const touchStart = new TouchEvent('touchstart', {
      touches: [{ clientX: 250, clientY: 200 } as unknown as Touch],
      bubbles: true
    })
    canvasEl.element.dispatchEvent(touchStart)

    const touchEnd = new TouchEvent('touchend', {
      changedTouches: [{ clientX: 150, clientY: 205 } as unknown as Touch],
      bubbles: true
    })
    canvasEl.element.dispatchEvent(touchEnd)

    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-test="slide-counter"]').text()).toContain('2 / 3')

    // Swipe right (return to prev slide) on current slide canvas
    const currentCanvas = wrapper.find('[data-test="presentation-slide-canvas"]')
    const touchStartRight = new TouchEvent('touchstart', {
      touches: [{ clientX: 100, clientY: 200 } as unknown as Touch],
      bubbles: true
    })
    currentCanvas.element.dispatchEvent(touchStartRight)

    const touchEndRight = new TouchEvent('touchend', {
      changedTouches: [{ clientX: 200, clientY: 195 } as unknown as Touch],
      bubbles: true
    })
    currentCanvas.element.dispatchEvent(touchEndRight)

    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-test="slide-counter"]').text()).toContain('1 / 3')
  })

  it('invokes toggleFullscreen once on "f" key inside dialog and detaches listener on unmount', async () => {
    const originalRequestFullscreen = HTMLElement.prototype.requestFullscreen
    const requestFullscreenMock = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(HTMLElement.prototype, 'requestFullscreen', {
      value: requestFullscreenMock,
      configurable: true,
      writable: true
    })

    const wrapper = mount(PresentationModal, {
      attachTo: document.body,
      props: {
        isOpen: true,
        content: sampleMarkdown,
        teleportDisabled: true
      }
    })

    try {
      const dialog = wrapper.find('dialog')
      expect(dialog.exists()).toBe(true)

      dialog.element.dispatchEvent(new KeyboardEvent('keydown', { key: 'f', bubbles: true }))
      await wrapper.vm.$nextTick()
      expect(requestFullscreenMock).toHaveBeenCalledTimes(1)

      wrapper.unmount()

      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'f', bubbles: true }))
      await wrapper.vm.$nextTick()
      expect(requestFullscreenMock).toHaveBeenCalledTimes(1)
    } finally {
      wrapper.unmount()
      Object.defineProperty(HTMLElement.prototype, 'requestFullscreen', {
        value: originalRequestFullscreen,
        configurable: true,
        writable: true
      })
    }
  })
})

