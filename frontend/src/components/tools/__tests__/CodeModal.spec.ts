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

  it('renders modal with code lines when open', () => {
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
    expect(wrapper.text()).toContain('Código')
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
    const removeSpy = vi.spyOn(HTMLAnchorElement.prototype, 'remove')

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
    expect(removeSpy).toHaveBeenCalled()
  })

  it('renders preview and code tabs when language is html', async () => {
    const htmlCode = '<h1>AbilaStore</h1><p>Bienvenidos</p>'
    const wrapper = mount(CodeModal, {
      props: {
        isOpen: true,
        code: htmlCode,
        language: 'html',
        extension: 'html',
        title: 'Maqueta Web',
        teleportDisabled: true
      }
    })

    const previewTab = wrapper.find('[data-test="code-tab-preview"]')
    const codeTab = wrapper.find('[data-test="code-tab-code"]')
    expect(previewTab.exists()).toBe(true)
    expect(codeTab.exists()).toBe(true)

    // Defaults to preview mode
    const iframe = wrapper.find('[data-test="code-modal-preview-iframe"]')
    expect(iframe.exists()).toBe(true)

    // Sandbox attributes: MUST have allow-scripts, MUST NOT have allow-same-origin or allow-top-navigation
    const sandboxAttr = iframe.attributes('sandbox') || ''
    expect(sandboxAttr).toContain('allow-scripts')
    expect(sandboxAttr).not.toContain('allow-same-origin')
    expect(sandboxAttr).not.toContain('allow-top-navigation')

    // CSP in srcdoc
    const srcdocAttr = iframe.attributes('srcdoc') || ''
    expect(srcdocAttr).toContain("connect-src 'none'")
    expect(srcdocAttr).toContain('AbilaStore')

    // Switch to code tab
    await codeTab.trigger('click')
    expect(wrapper.find('[data-test="code-modal-preview-iframe"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('AbilaStore')
  })

  it('creates html blob with text/html mime type when downloading html', async () => {
    let capturedOptions: BlobPropertyBag | undefined
    const originalBlob = global.Blob
    global.Blob = class MockBlob extends originalBlob {
      constructor(blobParts?: BlobPart[], options?: BlobPropertyBag) {
        super(blobParts, options)
        capturedOptions = options
      }
    } as unknown as typeof Blob

    global.URL.createObjectURL = vi.fn().mockReturnValue('blob:mock-url')
    global.URL.revokeObjectURL = vi.fn()
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

    const wrapper = mount(CodeModal, {
      props: {
        isOpen: true,
        code: '<!DOCTYPE html><html><body>AbilaStore</body></html>',
        language: 'html',
        extension: 'html',
        title: 'AbilaStore Demo',
        teleportDisabled: true
      }
    })

    const downloadBtn = wrapper.find('[data-test="code-modal-download-btn"]')
    await downloadBtn.trigger('click')

    expect(capturedOptions).toBeDefined()
    expect(capturedOptions?.type).toBe('text/html;charset=utf-8')

    global.Blob = originalBlob
  })
})