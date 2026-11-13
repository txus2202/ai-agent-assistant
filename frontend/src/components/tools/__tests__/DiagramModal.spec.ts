import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import DiagramModal from '../DiagramModal.vue'

// Mock mermaid library
vi.mock('mermaid', () => ({
  default: {
    initialize: vi.fn(),
    render: vi.fn().mockResolvedValue({ svg: '<svg class="mermaid-svg"><g>Test SVG</g></svg>' })
  }
}))

describe('DiagramModal.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined)
      }
    })
  })

  it('does not render modal when isOpen is false', () => {
    const wrapper = mount(DiagramModal, {
      props: {
        isOpen: false,
        code: 'flowchart TD\nA-->B'
      }
    })

    expect(wrapper.find('[data-test="diagram-modal-backdrop"]').exists()).toBe(false)
  })

  it('renders modal with backdrop and title when isOpen is true', () => {
    const wrapper = mount(DiagramModal, {
      props: {
        isOpen: true,
        code: 'flowchart TD\nA-->B'
      }
    })

    const dialog = wrapper.find('[data-test="diagram-modal-backdrop"]')
    expect(dialog.exists()).toBe(true)
    expect(dialog.element.tagName.toLowerCase()).toBe('dialog')
    expect(wrapper.text()).toContain('Diagrama')
  })

  it('emits close event when native dialog cancel event is triggered', async () => {
    const wrapper = mount(DiagramModal, {
      props: {
        isOpen: true,
        code: 'flowchart TD\nA-->B'
      }
    })

    const dialog = wrapper.find('dialog')
    await dialog.trigger('cancel')

    expect(wrapper.emitted('close')).toBeTruthy()
  })

  it('emits close event when close button is clicked', async () => {
    const wrapper = mount(DiagramModal, {
      props: {
        isOpen: true,
        code: 'flowchart TD\nA-->B'
      }
    })

    const closeBtn = wrapper.find('[data-test="diagram-modal-close-btn"]')
    expect(closeBtn.exists()).toBe(true)
    await closeBtn.trigger('click')

    expect(wrapper.emitted('close')).toBeTruthy()
  })

  it('emits close event when backdrop is clicked', async () => {
    const wrapper = mount(DiagramModal, {
      props: {
        isOpen: true,
        code: 'flowchart TD\nA-->B'
      }
    })

    const backdrop = wrapper.find('[data-test="diagram-modal-backdrop"]')
    await backdrop.trigger('click')

    expect(wrapper.emitted('close')).toBeTruthy()
  })

  it('emits close event when Escape key is pressed', async () => {
    const wrapper = mount(DiagramModal, {
      props: {
        isOpen: true,
        code: 'flowchart TD\nA-->B'
      },
      attachTo: document.body
    })

    const event = new KeyboardEvent('keydown', { key: 'Escape' })
    window.dispatchEvent(event)

    expect(wrapper.emitted('close')).toBeTruthy()
    wrapper.unmount()
  })

  it('copies code to clipboard and shows feedback when copy button is clicked', async () => {
    const code = 'flowchart TD\n  Client --> Server'
    const wrapper = mount(DiagramModal, {
      props: {
        isOpen: true,
        code
      }
    })

    const copyBtn = wrapper.find('[data-test="diagram-modal-copy-btn"]')
    expect(copyBtn.exists()).toBe(true)
    await copyBtn.trigger('click')

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(code)
    expect(wrapper.text()).toContain('Copiado')
  })

  it('adjusts zoom level when zoom in and zoom out buttons are clicked', async () => {
    const wrapper = mount(DiagramModal, {
      props: {
        isOpen: true,
        code: 'flowchart TD\nA-->B'
      }
    })

    const zoomInBtn = wrapper.find('[data-test="zoom-in-btn"]')
    const zoomOutBtn = wrapper.find('[data-test="zoom-out-btn"]')
    const zoomResetBtn = wrapper.find('[data-test="zoom-reset-btn"]')

    expect(zoomInBtn.exists()).toBe(true)
    expect(zoomOutBtn.exists()).toBe(true)
    expect(zoomResetBtn.exists()).toBe(true)

    // Initial zoom 100%
    expect(wrapper.find('[data-test="zoom-level-text"]').text()).toContain('100%')

    await zoomInBtn.trigger('click')
    expect(wrapper.find('[data-test="zoom-level-text"]').text()).toContain('110%')

    await zoomResetBtn.trigger('click')
    expect(wrapper.find('[data-test="zoom-level-text"]').text()).toContain('100%')

    await zoomOutBtn.trigger('click')
    expect(wrapper.find('[data-test="zoom-level-text"]').text()).toContain('90%')
  })

  it('downloads SVG diagram when clicking download button', async () => {
    global.URL.createObjectURL = vi.fn().mockReturnValue('blob:mock-svg-url')
    global.URL.revokeObjectURL = vi.fn()
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

    const wrapper = mount(DiagramModal, {
      props: {
        isOpen: true,
        code: 'flowchart TD\nA-->B',
        title: 'Mi Diagrama'
      }
    })
    await flushPromises()

    const downloadBtn = wrapper.find('[data-test="diagram-modal-download-btn"]')
    expect(downloadBtn.exists()).toBe(true)
    await downloadBtn.trigger('click')

    expect(global.URL.createObjectURL).toHaveBeenCalled()
    expect(clickSpy).toHaveBeenCalled()
  })
})
