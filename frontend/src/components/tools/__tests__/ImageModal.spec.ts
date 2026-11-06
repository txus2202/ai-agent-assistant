import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import ImageModal from '../ImageModal.vue'

describe('ImageModal.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('does not render when isOpen is false', () => {
    const wrapper = mount(ImageModal, {
      props: {
        isOpen: false,
        imageUrl: 'https://example.com/mockup.png',
        teleportDisabled: true
      }
    })
    expect(wrapper.find('[data-test="image-modal-backdrop"]').exists()).toBe(false)
  })

  it('renders modal with image when open', () => {
    const wrapper = mount(ImageModal, {
      props: {
        isOpen: true,
        imageUrl: 'https://example.com/mockup.png',
        alt: 'Mockup UI Fidias',
        title: 'Mockup UI Fidias',
        teleportDisabled: true
      }
    })

    expect(wrapper.find('[data-test="image-modal-backdrop"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Mockup UI Fidias')
    const img = wrapper.find('[data-test="image-modal-img"]')
    expect(img.attributes('src')).toBe('https://example.com/mockup.png')
    expect(img.attributes('alt')).toBe('Mockup UI Fidias')
  })

  it('supports zoom in, zoom out and reset zoom', async () => {
    const wrapper = mount(ImageModal, {
      props: {
        isOpen: true,
        imageUrl: 'https://example.com/mockup.png',
        teleportDisabled: true
      }
    })

    expect(wrapper.find('[data-test="image-zoom-level"]').text()).toBe('100%')

    await wrapper.find('[data-test="image-zoom-in-btn"]').trigger('click')
    expect(wrapper.find('[data-test="image-zoom-level"]').text()).toBe('120%')

    await wrapper.find('[data-test="image-zoom-out-btn"]').trigger('click')
    expect(wrapper.find('[data-test="image-zoom-level"]').text()).toBe('100%')

    await wrapper.find('[data-test="image-zoom-in-btn"]').trigger('click')
    await wrapper.find('[data-test="image-zoom-reset-btn"]').trigger('click')
    expect(wrapper.find('[data-test="image-zoom-level"]').text()).toBe('100%')
  })

  it('copies image url to clipboard on copy button click', async () => {
    const writeTextMock = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, {
      clipboard: {
        writeText: writeTextMock
      }
    })

    const wrapper = mount(ImageModal, {
      props: {
        isOpen: true,
        imageUrl: 'https://example.com/mockup.png',
        teleportDisabled: true
      }
    })

    const copyBtn = wrapper.find('[data-test="image-modal-copy-btn"]')
    await copyBtn.trigger('click')

    expect(writeTextMock).toHaveBeenCalledWith('https://example.com/mockup.png')
    expect(copyBtn.text()).toContain('Copiado')
  })

  it('emits close on close button click and escape key', async () => {
    const wrapper = mount(ImageModal, {
      props: {
        isOpen: true,
        imageUrl: 'https://example.com/mockup.png',
        teleportDisabled: true
      }
    })

    const closeBtn = wrapper.find('[data-test="image-modal-close-btn"]')
    await closeBtn.trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(wrapper.emitted('close')).toHaveLength(2)
  })
})

