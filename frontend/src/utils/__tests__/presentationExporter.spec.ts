import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  generateStandalonePresentationHtml,
  downloadPresentationHtml,
  downloadPresentationMarkdown,
  exportPresentationPptx
} from '../presentationExporter'
import type { PresentationData } from '../slideParser'

const mockWriteFile = vi.fn().mockResolvedValue('presentation.pptx')
const mockWrite = vi.fn().mockResolvedValue(new Blob(['mock-pptx'], { type: 'application/vnd.openxmlformats-officedocument.presentationml.presentation' }))
const mockAddText = vi.fn()
const mockAddShape = vi.fn()
const mockAddSlide = vi.fn().mockReturnValue({
  background: {},
  addText: mockAddText,
  addShape: mockAddShape
})

const lastInstance = { layout: '' }

vi.mock('pptxgenjs', () => {
  return {
    default: class MockPptxGen {
      ShapeType = { rect: 'rect' }
      addSlide = mockAddSlide
      writeFile = mockWriteFile
      write = mockWrite
      set layout(val: string) {
        lastInstance.layout = val
      }
      get layout(): string {
        return lastInstance.layout
      }
    }
  }
})

describe('presentationExporter.ts', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  const mockPresentation: PresentationData = {
    title: 'Arquitectura Atenea',
    slides: [
      {
        index: 1,
        title: 'Portada',
        subtitle: 'Sistema Centralizado',
        layout: 'hero',
        bullets: ['Punto inicial'],
        cards: [],
        raw: '## Portada\n> Sistema Centralizado'
      },
      {
        index: 2,
        title: 'Componentes',
        layout: 'cards',
        bullets: [],
        cards: [
          { title: 'PostgreSQL', content: 'Base de datos primaria' },
          { title: 'Redis', content: 'Caché en memoria' }
        ],
        raw: '## Componentes'
      }
    ]
  }

  it('generates a complete standalone HTML document with slides and controls', () => {
    const html = generateStandalonePresentationHtml(mockPresentation)

    expect(html).toContain('<!DOCTYPE html>')
    expect(html).toContain('<title>Arquitectura Atenea</title>')
    expect(html).toContain('Portada')
    expect(html).toContain('Sistema Centralizado')
    expect(html).toContain('Componentes')
    expect(html).toContain('PostgreSQL')
    expect(html).toContain('Redis')
    expect(html).toContain('@media print')
    expect(html).toContain('addEventListener')
    expect(html).not.toContain('cdn.jsdelivr.net')
    expect(html).not.toMatch(/<script[^>]+src=/i)
    expect(html).toContain('<style>')
    expect(html).toContain('.pres-card')
  })

  it('triggers download for HTML presentation file', () => {
    vi.useFakeTimers()
    const createObjectURLMock = vi.fn().mockReturnValue('blob:mock-html-url')
    const revokeObjectURLMock = vi.fn()
    global.URL.createObjectURL = createObjectURLMock
    global.URL.revokeObjectURL = revokeObjectURLMock
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const appendSpy = vi.spyOn(document.body, 'appendChild')
    const removeSpy = vi.spyOn(HTMLAnchorElement.prototype, 'remove')

    downloadPresentationHtml(mockPresentation, 'presentacion_test')

    expect(createObjectURLMock).toHaveBeenCalled()
    expect(clickSpy).toHaveBeenCalled()
    expect(appendSpy).toHaveBeenCalled()

    vi.runAllTimers()
    expect(removeSpy).toHaveBeenCalled()
    expect(revokeObjectURLMock).toHaveBeenCalledWith('blob:mock-html-url')
    vi.useRealTimers()
  })

  it('triggers download for Markdown presentation file', () => {
    vi.useFakeTimers()
    const createObjectURLMock = vi.fn().mockReturnValue('blob:mock-md-url')
    const revokeObjectURLMock = vi.fn()
    global.URL.createObjectURL = createObjectURLMock
    global.URL.revokeObjectURL = revokeObjectURLMock
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

    downloadPresentationMarkdown('# Slide 1', 'presentacion_raw')

    expect(createObjectURLMock).toHaveBeenCalled()
    expect(clickSpy).toHaveBeenCalled()
    vi.runAllTimers()
    expect(revokeObjectURLMock).toHaveBeenCalledWith('blob:mock-md-url')
    vi.useRealTimers()
  })

  it('exports presentation to PowerPoint .pptx format using pptxgenjs', async () => {
    const createObjectURLMock = vi.fn().mockReturnValue('blob:mock-pptx-url')
    global.URL.createObjectURL = createObjectURLMock
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

    await exportPresentationPptx(mockPresentation, 'arquitectura_atenea')

    expect(lastInstance?.layout).toBe('LAYOUT_WIDE')
    expect(mockAddSlide).toHaveBeenCalledTimes(2)
    expect(mockAddText).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({ fit: 'shrink' }))
    expect(mockWrite).toHaveBeenCalledWith({ outputType: 'blob' })
    expect(createObjectURLMock).toHaveBeenCalled()
    expect(clickSpy).toHaveBeenCalled()
  })

  it('uses default filename if not provided in pptx export', async () => {
    const createObjectURLMock = vi.fn().mockReturnValue('blob:mock-pptx-url')
    global.URL.createObjectURL = createObjectURLMock
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

    const dataWithoutTitle: PresentationData = {
      title: '',
      slides: [
        {
          index: 1,
          title: 'Slide Solo',
          layout: 'standard',
          bullets: [],
          cards: [],
          raw: '## Slide Solo'
        }
      ]
    }

    await exportPresentationPptx(dataWithoutTitle)

    expect(mockWrite).toHaveBeenCalledWith({ outputType: 'blob' })
    expect(createObjectURLMock).toHaveBeenCalled()
    expect(clickSpy).toHaveBeenCalled()
  })
})

