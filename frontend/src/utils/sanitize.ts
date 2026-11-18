import DOMPurify, { type Config } from 'dompurify'

const FORBIDDEN_EVENT_ATTRS = [
  'onerror',
  'onload',
  'onclick',
  'onmouseover',
  'onfocus',
  'onblur',
  'onsubmit',
  'formaction',
]

const HTML_SANITIZE_CONFIG: Config = {
  USE_PROFILES: { html: true },
  FORBID_TAGS: [
    'script',
    'style',
    'iframe',
    'object',
    'embed',
    'form',
    'input',
    'textarea',
    'select',
    'button',
    'foreignObject',
  ],
  FORBID_ATTR: FORBIDDEN_EVENT_ATTRS,
}

const SVG_SANITIZE_CONFIG: Config = {
  USE_PROFILES: { svg: true, svgFilters: true },
  FORBID_TAGS: ['script', 'foreignObject', 'iframe', 'object', 'embed'],
  FORBID_ATTR: FORBIDDEN_EVENT_ATTRS,
}

export function sanitizeHtml(html: string): string {
  if (!html) return ''
  return DOMPurify.sanitize(html, HTML_SANITIZE_CONFIG)
}

export function sanitizeSvg(svg: string): string {
  if (!svg) return ''
  return DOMPurify.sanitize(svg, SVG_SANITIZE_CONFIG)
}

export function sanitizeHtmlToFragment(html: string): DocumentFragment {
  return DOMPurify.sanitize(html || '', {
    ...HTML_SANITIZE_CONFIG,
    RETURN_DOM_FRAGMENT: true,
  })
}

