import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import CodeModal from '../CodeModal.vue'

describe('CodeModal.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('does not render when isOpen is false', () => {
    const wrapper = mount(CodeModal, {
      props: {
        isOpen: false,
        code: 'console.log("hello")',
        teleportDisabled: true
      }
    })
    expect(wrapper.find('[data-test="code-modal-backdrop"]').exists()).toBe(false)
  })

  it('renders modal with code lines and language extension badge when open', () => {
    const code = 'package main\n\nfunc main() {\n\tprintln("Dédalo")\n}'
    const wrapper = mount(CodeModal, {
      props: {
        isOpen: true,
        code,
        language: 'go',
        extension: 'go',
        title: 'Código Go de Dédalo',
        teleportDisabled: true
      }
    })

    expect(wrapper.find('[data-test="code-modal-backdrop"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Código Go de Dédalo')
    expect(wrapper.find('[data-test="code-modal-badge"]').text()).toBe('.go')
    expect(wrapper.text()).toContain('println("Dédalo")')
  })

  it('copies code to clipboard on copy button click', async () => {
    const writeTextMock = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, {
      clipboard: {
        writeText: writeTextMock
      }
    })

    const code = 'const pi = 3.14159'
    const wrapper = mount(CodeModal, {
      props: {
        isOpen: true,
        code,
        language: 'typescript',
        teleportDisabled: true
      }
    })

    const copyBtn = wrapper.find('[data-test="code-modal-copy-btn"]')
    await copyBtn.trigger('click')

    expect(writeTextMock).toHaveBeenCalledWith(code)
    expect(copyBtn.text()).toContain('Copiado')
  })

  it('emits close on close button click and escape key', async () => {
    const wrapper = mount(CodeModal, {
      props: {
        isOpen: true,
        code: 'const a = 1',
        teleportDisabled: true
      }
    })

    const closeBtn = wrapper.find('[data-test="code-modal-close-btn"]')
    await closeBtn.trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)

    // Escape key
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(wrapper.emitted('close')).toHaveLength(2)
  })

  it('triggers download with proper extension when download button is clicked', async () => {
    global.URL.createObjectURL = vi.fn().mockReturnValue('blob:mock-url')
    global.URL.revokeObjectURL = vi.fn()
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const appendChildSpy = vi.spyOn(document.body, 'appendChild')
    const removeChildSpy = vi.spyOn(document.body, 'removeChild')

    const wrapper = mount(CodeModal, {
      props: {
        isOpen: true,
        code: '<template><div>Fidias</div></template>',
        language: 'vue',
        extension: 'vue',
        title: 'Componente Fidias',
        teleportDisabled: true
      }
    })

    const downloadBtn = wrapper.find('[data-test="code-modal-download-btn"]')
    await downloadBtn.trigger('click')

    expect(clickSpy).toHaveBeenCalled()
    expect(appendChildSpy).toHaveBeenCalled()
    expect(removeChildSpy).toHaveBeenCalled()
  })
})