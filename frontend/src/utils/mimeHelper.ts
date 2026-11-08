/**
 * Utility for resolving MIME types and preparing secure sandboxed HTML payloads.
 */

const EXTENSION_MIME_MAP: Record<string, string> = {
  html: 'text/html;charset=utf-8',
  htm: 'text/html;charset=utf-8',
  svg: 'image/svg+xml;charset=utf-8',
  json: 'application/json;charset=utf-8',
  md: 'text/markdown;charset=utf-8',
  markdown: 'text/markdown;charset=utf-8',
  js: 'application/javascript;charset=utf-8',
  mjs: 'application/javascript;charset=utf-8',
  ts: 'text/plain;charset=utf-8',
  css: 'text/css;charset=utf-8',
  xml: 'application/xml;charset=utf-8',
  csv: 'text/csv;charset=utf-8',
  txt: 'text/plain;charset=utf-8',
}

const DEFAULT_MIME_TYPE = 'text/plain;charset=utf-8'

/**
 * Returns the MIME type corresponding to a given file extension.
 * Defaults to text/plain;charset=utf-8.
 */
export function getMimeTypeForExtension(extension?: string): string {
  if (!extension) return DEFAULT_MIME_TYPE
  const cleanExt = extension.toLowerCase().replace(/^\./, '').trim()
  return EXTENSION_MIME_MAP[cleanExt] || DEFAULT_MIME_TYPE
}

/**
 * Strict Content-Security-Policy to inject into HTML previews.
 * - Disallows outgoing network connections (connect-src 'none') to prevent data exfiltration.
 * - Disallows plugins (object-src 'none').
 * - Disallows base-uri hijacking (base-uri 'none').
 * - Allows self and inline styles/scripts for rich layout interaction.
 */
export const STRICT_SANDBOX_CSP =
  `<meta http-equiv="Content-Security-Policy" content="default-src 'self' 'unsafe-inline' data: https:; connect-src 'none'; object-src 'none'; base-uri 'none';">`

/**
 * Prepares raw HTML for secure iframe rendering by injecting the strict CSP.
 * Injects into <head> if present, or prepends at the start of the document.
 */
export function prepareSandboxedHtml(rawHtml: string): string {
  if (!rawHtml?.trim()) return ''

  const headMatch = /<head[^>]*>/i.exec(rawHtml)
  if (headMatch) {
    const insertIdx = headMatch.index + headMatch[0].length
    return (
      rawHtml.slice(0, insertIdx) +
      '\n  ' +
      STRICT_SANDBOX_CSP +
      rawHtml.slice(insertIdx)
    )
  }

  return `${STRICT_SANDBOX_CSP}\n${rawHtml}`
}

