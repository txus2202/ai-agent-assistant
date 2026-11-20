import { describe, it, expect } from 'vitest'
import { sanitizeHtml, sanitizeSvg, sanitizeHtmlToFragment } from '../sanitize'

describe('sanitize.ts', () => {
  it('strips script tags, dangerous tags, inline handlers and javascript URIs from HTML', () => {
    const dirty = [
      '<h1 class="doc-h1">Título</h1>',
      '<script>alert(1)</script>',
      '<img src="x" onerror="alert(2)">',
      '<a href="javascript:alert(3)" onclick="alert(4)">Click</a>',
      '<iframe src="https://evil.example"></iframe>',
      '<svg onload="alert(5)"><foreignObject><div>XSS</div></foreignObject></svg>',
      '<p class="doc-p">Contenido seguro</p>',
    ].join('')

    const clean = sanitizeHtml(dirty)
    expect(clean).toContain('<h1 class="doc-h1">Título</h1>')
    expect(clean).toContain('<p class="doc-p">Contenido seguro</p>')
    expect(clean).not.toContain('<script')
    expect(clean).not.toContain('onerror')
    expect(clean).not.toContain('onload')
    expect(clean).not.toContain('onclick')
    expect(clean).not.toContain('javascript:')
    expect(clean).not.toContain('<iframe')
    expect(clean).not.toContain('<foreignObject')
    expect(clean).not.toContain('foreignobject')
  })

  it('preserves safe foreignObject and HTML text labels used by Mermaid diagrams while stripping script, iframe, and event handlers', () => {
    const mermaidSvg =
      '<svg viewBox="0 0 100 100" onload="alert(1)"><g><rect x="0" y="0" width="10" height="10" onclick="alert(2)"/><text x="5" y="5">Native Text</text></g><script>alert(3)</script><foreignObject width="120" height="30"><div xmlns="http://www.w3.org/1999/xhtml"><span class="nodeLabel">Cliente Web</span><script>alert(4)</script><img src="x" onerror="alert(5)"/><a href="javascript:alert(6)" onclick="alert(7)">link</a><iframe src="https://evil.com"></iframe></div></foreignObject></svg>'

    const clean = sanitizeSvg(mermaidSvg)
    expect(clean).toContain('<svg')
    expect(clean).toContain('<rect')
    expect(clean).toContain('Native Text')
    expect(clean).toContain('<foreignObject')
    expect(clean).toContain('Cliente Web')
    expect(clean).toContain('class="nodeLabel"')
    expect(clean).not.toContain('<script')
    expect(clean).not.toContain('alert(')
    expect(clean).not.toContain('onload')
    expect(clean).not.toContain('onclick')
    expect(clean).not.toContain('onerror')
    expect(clean).not.toContain('javascript:')
    expect(clean).not.toContain('<iframe')
  })

  it('builds a sanitized DocumentFragment without active nodes', () => {
    const frag = sanitizeHtmlToFragment('<p class="doc-p">Ok</p><script>evil()</script><img src=x onerror=evil()>')
    const container = document.createElement('div')
    container.appendChild(frag)
    expect(container.querySelector('script')).toBeNull()
    expect(container.querySelector('img')?.getAttribute('onerror')).toBeNull()
    expect(container.querySelector('p.doc-p')?.textContent).toBe('Ok')
  })
})

