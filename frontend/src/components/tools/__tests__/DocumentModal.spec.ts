import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import DocumentModal from '../DocumentModal.vue'

describe('DocumentModal.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined)
      }
    })
  })

  it('does not render modal when isOpen is false', () => {
    const wrapper = mount(DocumentModal, {
      props: {
        isOpen: false,
        content: '# Titulo\nTexto de prueba',
        teleportDisabled: true
      }
    })

    expect(wrapper.find('[data-test="document-modal-backdrop"]').exists()).toBe(false)
  })

  it('renders modal with title, rendered preview, and tabs when isOpen is true', () => {
    const wrapper = mount(DocumentModal, {
      props: {
        isOpen: true,
        content: '# Especificación del Sistema\n\nEste es el contenido de prueba.',
        title: 'Especificación del Sistema',
        teleportDisabled: true
      }
    })

    expect(wrapper.find('[data-test="document-modal-backdrop"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Especificación del Sistema')
    expect(wrapper.find('[data-test="document-preview-container"]').exists()).toBe(true)
  })

  it('toggles between preview and raw markdown tabs', async () => {
    const wrapper = mount(DocumentModal, {
      props: {
        isOpen: true,
        content: '# Titulo\nLinea 1\nLinea 2',
        teleportDisabled: true
      }
    })

    expect(wrapper.find('[data-test="document-preview-container"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="document-raw-container"]').exists()).toBe(false)

    // Switch to raw tab
    await wrapper.find('[data-test="doc-tab-raw"]').trigger('click')
    expect(wrapper.find('[data-test="document-preview-container"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="document-raw-container"]').exists()).toBe(true)

    // Switch back to preview
    await wrapper.find('[data-test="doc-tab-preview"]').trigger('click')
    expect(wrapper.find('[data-test="document-preview-container"]').exists()).toBe(true)
  })

  it('copies markdown content on copy button click', async () => {
    const writeTextMock = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, {
      clipboard: {
        writeText: writeTextMock
      }
    })

    const content = '# Reporte Calíope\nDocumentación detallada.'
    const wrapper = mount(DocumentModal, {
      props: {
        isOpen: true,
        content,
        teleportDisabled: true
      }
    })

    const copyBtn = wrapper.find('[data-test="document-modal-copy-btn"]')
    await copyBtn.trigger('click')

    expect(writeTextMock).toHaveBeenCalledWith(content)
    expect(copyBtn.text()).toContain('Copiado')
  })

  it('triggers download .md and export pdf functions on click', async () => {
    global.URL.createObjectURL = vi.fn().mockReturnValue('blob:mock-url')
    global.URL.revokeObjectURL = vi.fn()
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const openSpy = vi.spyOn(window, 'open').mockReturnValue({
      document: {
        documentElement: { innerHTML: '' },
      },
      focus: vi.fn(),
      print: vi.fn()
    } as unknown as Window)

    const wrapper = mount(DocumentModal, {
      props: {
        isOpen: true,
        content: '# Manual de Usuario\nPasos a seguir.',
        title: 'Manual de Usuario',
        teleportDisabled: true
      }
    })

    // Click Download MD
    await wrapper.find('[data-test="document-modal-download-md-btn"]').trigger('click')
    expect(clickSpy).toHaveBeenCalled()

    // Click Export PDF
    await wrapper.find('[data-test="document-modal-export-pdf-btn"]').trigger('click')
    expect(openSpy).toHaveBeenCalled()

    // Also supports download dropdown with .pdf and .md options
    const dropdownBtn = wrapper.find('[data-test="document-modal-download-menu-btn"]')
    expect(dropdownBtn.exists()).toBe(true)
    await dropdownBtn.trigger('click')
    expect(wrapper.find('[data-test="document-download-dropdown"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="document-download-option-pdf"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="document-download-option-md"]').exists()).toBe(true)
  })

  it('emits close on close button click and escape key', async () => {
    const wrapper = mount(DocumentModal, {
      props: {
        isOpen: true,
        content: '# Manual',
        teleportDisabled: true
      }
    })

    await wrapper.find('[data-test="document-modal-close-btn"]').trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)

    // Escape key
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(wrapper.emitted('close')).toHaveLength(2)
  })
})

