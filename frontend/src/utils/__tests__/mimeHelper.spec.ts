import { describe, it, expect } from 'vitest'
import {
  getMimeTypeForExtension,
  prepareSandboxedHtml,
  STRICT_SANDBOX_CSP
} from '../mimeHelper'

describe('getMimeTypeForExtension', () => {
  it('returns text/html;charset=utf-8 for html and htm', () => {
    expect(getMimeTypeForExtension('html')).toBe('text/html;charset=utf-8')
    expect(getMimeTypeForExtension('htm')).toBe('text/html;charset=utf-8')
    expect(getMimeTypeForExtension('.html')).toBe('text/html;charset=utf-8')
    expect(getMimeTypeForExtension('HTML')).toBe('text/html;charset=utf-8')
  })

  it('returns image/svg+xml;charset=utf-8 for svg', () => {
    expect(getMimeTypeForExtension('svg')).toBe('image/svg+xml;charset=utf-8')
    expect(getMimeTypeForExtension('.svg')).toBe('image/svg+xml;charset=utf-8')
  })

  it('returns application/json;charset=utf-8 for json', () => {
    expect(getMimeTypeForExtension('json')).toBe('application/json;charset=utf-8')
  })

  it('returns text/markdown;charset=utf-8 for md and markdown', () => {
    expect(getMimeTypeForExtension('md')).toBe('text/markdown;charset=utf-8')
    expect(getMimeTypeForExtension('markdown')).toBe('text/markdown;charset=utf-8')
  })

  it('returns text/css;charset=utf-8 for css', () => {
    expect(getMimeTypeForExtension('css')).toBe('text/css;charset=utf-8')
  })

  it('returns application/javascript;charset=utf-8 for js and mjs', () => {
    expect(getMimeTypeForExtension('js')).toBe('application/javascript;charset=utf-8')
    expect(getMimeTypeForExtension('mjs')).toBe('application/javascript;charset=utf-8')
  })

  it('falls back to text/plain;charset=utf-8 for unknown or empty extensions', () => {
    expect(getMimeTypeForExtension('')).toBe('text/plain;charset=utf-8')
    expect(getMimeTypeForExtension(undefined)).toBe('text/plain;charset=utf-8')
    expect(getMimeTypeForExtension('unknown_ext')).toBe('text/plain;charset=utf-8')
  })
})

describe('prepareSandboxedHtml', () => {
  it('returns empty string if input is empty or whitespace', () => {
    expect(prepareSandboxedHtml('')).toBe('')
    expect(prepareSandboxedHtml('   ')).toBe('')
  })

  it('injects CSP meta tag directly inside <head> when present', () => {
    const raw = `<!DOCTYPE html>
<html lang="es">
<head>
  <title>AbilaStore</title>
</head>
<body>
  <h1>Hola</h1>
</body>
</html>`

    const result = prepareSandboxedHtml(raw)
    expect(result).toContain(STRICT_SANDBOX_CSP)
    expect(result).toMatch(/<head>\s*<meta http-equiv="Content-Security-Policy"/)
    expect(result).toContain("connect-src 'none'")
  })

  it('prepends CSP meta tag if no <head> tag exists in snippet', () => {
    const raw = '<div class="banner">Ofertas</div><style>.banner { color: red; }</style>'
    const result = prepareSandboxedHtml(raw)
    expect(result.startsWith(STRICT_SANDBOX_CSP)).toBe(true)
    expect(result).toContain('<div class="banner">Ofertas</div>')
    expect(result).toContain("connect-src 'none'")
  })
})

