import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import DiagramViewport from '../DiagramViewport.vue'
import DocumentContentPane from '../DocumentContentPane.vue'
import PresentationSlideStage from '../PresentationSlideStage.vue'
import PresentationToolbar from '../PresentationToolbar.vue'

describe('Tool modal subcomponents', () => {
  it('PresentationToolbar emits toolbar controls and download options', async () => {
    const wrapper = mount(PresentationToolbar, {
      props: {
        isFullscreen: false,
        isCopied: false,
        isExportingPptx: false,
        isDownloadMenuOpen: true,
      },
    })

    await wrapper.find('[data-test="presentation-modal-fullscreen-btn"]').trigger('click')
    await wrapper.find('[data-test="presentation-modal-copy-btn"]').trigger('click')
    await wrapper.find('[data-test="download-option-md"]').trigger('click')

    expect(wrapper.emitted('toggle-fullscreen')).toHaveLength(1)
    expect(wrapper.emitted('copy')).toHaveLength(1)
    expect(wrapper.emitted('download-markdown')).toHaveLength(1)
  })

  it('PresentationSlideStage renders slide cards and emits prev/next/go-to', async () => {
    const wrapper = mount(PresentationSlideStage, {
      props: {
        currentSlide: {
          index: 2,
          title: 'Topología Hexagonal',
          layout: 'cards',
          cards: [
            { title: 'Dominio', badge: 'CORE', content: 'Reglas puras' },
            { title: 'Puertos', content: 'Interfaces' },
          ],
          bullets: [],
          notes: 'Validado por SPHINX',
          raw: '## Topología Hexagonal',
        },
        currentSlideIndex: 2,
        totalSlides: 3,
        slideDirection: 'forward',
      },
    })

    expect(wrapper.text()).toContain('Topología Hexagonal')
    expect(wrapper.text()).toContain('Dominio')
    expect(wrapper.find('[data-test="slide-counter"]').text()).toBe('2 / 3')

    await wrapper.find('[data-test="slide-prev-btn"]').trigger('click')
    await wrapper.find('[data-test="slide-next-btn"]').trigger('click')
    expect(wrapper.emitted('prev')).toHaveLength(1)
    expect(wrapper.emitted('next')).toHaveLength(1)
  })

  it('DocumentContentPane switches cleanly between preview and raw lines', () => {
    const preview = mount(DocumentContentPane, {
      props: {
        activeTab: 'preview',
        renderedHtml: '<h1 class="doc-h1">Guía</h1>',
        rawLines: ['# Guía'],
      },
    })
    expect(preview.find('[data-test="document-preview-container"]').text()).toContain('Guía')

    const raw = mount(DocumentContentPane, {
      props: {
        activeTab: 'raw',
        renderedHtml: '',
        rawLines: ['# Guía', 'Línea 2'],
      },
    })
    expect(raw.find('[data-test="document-raw-container"]').text()).toContain('Línea 2')
  })

  it('DiagramViewport displays error, svg, or loading spinner depending on props', () => {
    const errorView = mount(DiagramViewport, {
      props: {
        renderError: 'Syntax error',
        diagramSvg: '',
        code: 'invalid graph',
        zoomLevel: 1,
      },
    })
    expect(errorView.text()).toContain('Error al renderizar el diagrama')
    expect(errorView.text()).toContain('Syntax error')

    const svgView = mount(DiagramViewport, {
      props: {
        renderError: null,
        diagramSvg: '<svg><text>Diagrama OK</text></svg>',
        code: 'graph TD; A-->B',
        zoomLevel: 1.5,
      },
    })
    const svgEl = svgView.find('[data-test="rendered-diagram-svg"]')
    expect(svgEl.attributes('style')).toContain('scale(1.5)')
  })
})
