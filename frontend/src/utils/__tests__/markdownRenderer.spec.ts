import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  extractDocumentTitle,
  renderMarkdownToHtml,
  downloadMarkdownFile,
  exportDocumentToPdf,
} from '../markdownRenderer'

describe('markdownRenderer.ts', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('extracts document title from markdown heading or returns fallback', () => {
    expect(extractDocumentTitle('# Manual de Usuario\nContenido')).toBe('Manual de Usuario')
    expect(extractDocumentTitle('## Especificación de Arquitectura\nContenido')).toBe('Especificación de Arquitectura')
    expect(extractDocumentTitle('Solo texto sin encabezado', 'Mi Reporte')).toBe('Mi Reporte')
    expect(extractDocumentTitle('', 'Fallback')).toBe('Fallback')
  })

  it('renders headings and paragraphs into html', () => {
    const md = '# Titulo 1\n## Titulo 2\n### Titulo 3\nEste es un parrafo.'
    const html = renderMarkdownToHtml(md)
    expect(html).toContain('<h1 class="doc-h1">Titulo 1</h1>')
    expect(html).toContain('<h2 class="doc-h2">Titulo 2</h2>')
    expect(html).toContain('<h3 class="doc-h3">Titulo 3</h3>')
    expect(html).toContain('<p class="doc-p">Este es un parrafo.</p>')
  })

  it('renders inline elements: bold, italic, and inline code', () => {
    const md = 'Texto con **negrita**, *cursiva* y `codigo_inline`.'
    const html = renderMarkdownToHtml(md)
    expect(html).toContain('<strong>negrita</strong>')
    expect(html).toContain('<em>cursiva</em>')
    expect(html).toContain('<code class="doc-inline-code">codigo_inline</code>')
  })

  it('renders unordered and ordered lists', () => {
    const md = '- Item A\n- Item B\n\n1. Paso 1\n2. Paso 2'
    const html = renderMarkdownToHtml(md)
    expect(html).toContain('<ul class="doc-ul">')
    expect(html).toContain('<li>Item A</li>')
    expect(html).toContain('<li>Item B</li>')
    expect(html).toContain('</ul>')
    expect(html).toContain('<ol class="doc-ol">')
    expect(html).toContain('<li>Paso 1</li>')
    expect(html).toContain('<li>Paso 2</li>')
    expect(html).toContain('</ol>')
  })

  it('renders fenced code blocks and blockquotes', () => {
    const md = '> Esta es una cita importante.\n\n```python\ndef saludo():\n    return "hola"\n```'
    const html = renderMarkdownToHtml(md)
    expect(html).toContain('<blockquote class="doc-blockquote">')
    expect(html).toContain('<pre class="doc-code-block"><code class="language-python">def saludo():\n    return "hola"</code></pre>')
  })

  it('renders markdown tables correctly', () => {
    const md = '| Parámetro | Tipo | Descripción |\n|---|---|---|\n| id | string | Identificador único |'
    const html = renderMarkdownToHtml(md)
    expect(html).toContain('<table class="doc-table">')
    expect(html).toContain('<th>Parámetro</th>')
    expect(html).toContain('<td>Identificador único</td>')
  })

  it('downloads markdown file with proper link creation', () => {
    global.URL.createObjectURL = vi.fn().mockReturnValue('blob:mock-url')
    global.URL.revokeObjectURL = vi.fn()
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const appendSpy = vi.spyOn(document.body, 'appendChild')
    const removeSpy = vi.spyOn(HTMLAnchorElement.prototype, 'remove').mockImplementation(() => {})

    downloadMarkdownFile('# Titulo\nContenido', 'manual_tecnico')

    expect(clickSpy).toHaveBeenCalled()
    expect(appendSpy).toHaveBeenCalled()
    expect(removeSpy).toHaveBeenCalled()
  })

  it('opens a print window and builds safe DOM when exporting to PDF', () => {
    const printMock = vi.fn()
    const focusMock = vi.fn()
    const printDoc = document.implementation.createHTMLDocument('')
    const openMock = vi.spyOn(window, 'open').mockReturnValue({
      document: printDoc,
      print: printMock,
      focus: focusMock,
    } as unknown as Window)

    exportDocumentToPdf('# Reporte de Arquitectura\n<script>alert(1)</script>Texto', 'Título <script>xss</script>')

    expect(openMock).toHaveBeenCalled()
    expect(printMock).toHaveBeenCalled()
    expect(printDoc.title).toBe('Título <script>xss</script>')
    expect(printDoc.querySelector('main script')).toBeNull()
    expect(printDoc.querySelector('h1.doc-h1')?.textContent).toBe('Reporte de Arquitectura')
    expect(printDoc.querySelector('.doc-footer')).not.toBeNull()
  })
})

