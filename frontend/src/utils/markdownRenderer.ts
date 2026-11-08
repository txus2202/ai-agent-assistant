/**
 * Lightweight, safe Markdown to HTML renderer for DocumentViewer and PDF export.
 * Zero external dependencies.
 */

function escapeHtml(text: string): string {
  return text
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

export function extractDocumentTitle(markdown: string, fallback: string = 'Documento'): string {
  if (!markdown) return fallback
  const lines = markdown.split('\n')
  for (const line of lines) {
    const trimmed = line.trim()
    if (trimmed.startsWith('# ')) {
      return trimmed.replace(/^#\s+/, '').trim() || fallback
    }
    if (trimmed.startsWith('## ')) {
      return trimmed.replace(/^##\s+/, '').trim() || fallback
    }
  }
  return fallback
}

function extractCodeBlocks(markdown: string): { processed: string; codeBlocks: string[] } {
  const codeBlocks: string[] = []
  const processed = markdown.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, (_, lang, code) => {
    const safeLang = escapeHtml(lang || '')
    const safeCode = escapeHtml(code.trimEnd())
    const placeholder = `__CODE_BLOCK_${codeBlocks.length}__`
    codeBlocks.push(
      `<pre class="doc-code-block"><code class="language-${safeLang}">${safeCode}</code></pre>`
    )
    return placeholder
  })
  return { processed, codeBlocks }
}

function renderTableBlock(tableBlock: string): string {
  const rawLines = tableBlock.trim().split('\n').filter(l => l.trim().startsWith('|'))
  const firstLine = rawLines[0]
  const secondLine = rawLines[1]
  if (!firstLine || !secondLine) return tableBlock

  const isDivider = /^\|(?:\s*:?-+:?\s*\|)+$/.test(secondLine.trim())
  if (!isDivider) return tableBlock

  const headerCols = firstLine
    .split('|')
    .slice(1, -1)
    .map(c => `<th>${escapeHtml(c.trim())}</th>`)
    .join('')

  const bodyRows = rawLines.slice(2).map(row => {
    const cols = row
      .split('|')
      .slice(1, -1)
      .map(c => `<td>${escapeHtml(c.trim())}</td>`)
      .join('')
    return `<tr>${cols}</tr>`
  }).join('')

  return `<table class="doc-table"><thead><tr>${headerCols}</tr></thead><tbody>${bodyRows}</tbody></table>`
}

function renderMarkdownTables(text: string): string {
  return text.replace(/((?:\|[^\n]+\|\n?)+)/g, renderTableBlock)
}

function getHeadingHtml(trimmed: string): string | null {
  if (trimmed.startsWith('# ')) {
    return `<h1 class="doc-h1">${formatInline(trimmed.slice(2))}</h1>`
  }
  if (trimmed.startsWith('## ')) {
    return `<h2 class="doc-h2">${formatInline(trimmed.slice(3))}</h2>`
  }
  if (trimmed.startsWith('### ')) {
    return `<h3 class="doc-h3">${formatInline(trimmed.slice(4))}</h3>`
  }
  if (trimmed.startsWith('#### ')) {
    return `<h4 class="doc-h4">${formatInline(trimmed.slice(5))}</h4>`
  }
  return null
}

export function renderMarkdownToHtml(markdown: string): string {
  if (!markdown) return ''

  const { processed, codeBlocks } = extractCodeBlocks(markdown)
  const textWithTables = renderMarkdownTables(processed)

  const lines = textWithTables.split('\n')
  const output: string[] = []
  let inUl = false
  let inOl = false
  let inBlockquote = false

  const closeLists = () => {
    if (inUl) {
      output.push('</ul>')
      inUl = false
    }
    if (inOl) {
      output.push('</ol>')
      inOl = false
    }
  }

  const closeBlockquote = () => {
    if (inBlockquote) {
      output.push('</blockquote>')
      inBlockquote = false
    }
  }

  for (const line of lines) {
    const trimmed = (line || '').trim()

    if (trimmed.startsWith('__CODE_BLOCK_') && trimmed.endsWith('__')) {
      closeLists()
      closeBlockquote()
      output.push(trimmed)
      continue
    }

    if (trimmed.startsWith('<table class="doc-table">') || trimmed.startsWith('</table>') || trimmed.startsWith('<thead>') || trimmed.startsWith('<tbody>') || trimmed.startsWith('<tr>')) {
      closeLists()
      closeBlockquote()
      output.push(trimmed)
      continue
    }

    if (!trimmed) {
      closeLists()
      closeBlockquote()
      continue
    }

    if (trimmed.startsWith('> ')) {
      closeLists()
      if (!inBlockquote) {
        output.push('<blockquote class="doc-blockquote">')
        inBlockquote = true
      }
      output.push(`<p>${formatInline(trimmed.slice(2))}</p>`)
      continue
    }
    closeBlockquote()

    const headingHtml = getHeadingHtml(trimmed)
    if (headingHtml) {
      closeLists()
      output.push(headingHtml)
      continue
    }

    if (/^(\*\*\*|---|___)$/.test(trimmed)) {
      closeLists()
      output.push('<hr class="doc-hr" />')
      continue
    }

    if (/^[-*+]\s+/.test(trimmed)) {
      if (inOl) {
        output.push('</ol>')
        inOl = false
      }
      if (!inUl) {
        output.push('<ul class="doc-ul">')
        inUl = true
      }
      output.push(`<li>${formatInline(trimmed.replace(/^[-*+]\s+/, ''))}</li>`)
      continue
    }

    if (/^\d+\.\s+/.test(trimmed)) {
      if (inUl) {
        output.push('</ul>')
        inUl = false
      }
      if (!inOl) {
        output.push('<ol class="doc-ol">')
        inOl = true
      }
      output.push(`<li>${formatInline(trimmed.replace(/^\d+\.\s+/, ''))}</li>`)
      continue
    }

    closeLists()
    output.push(`<p class="doc-p">${formatInline(trimmed)}</p>`)
  }

  closeLists()
  closeBlockquote()

  let finalHtml = output.join('\n')
  codeBlocks.forEach((block, index) => {
    finalHtml = finalHtml.replaceAll(`__CODE_BLOCK_${index}__`, block)
  })

  return finalHtml
}

function formatInline(text: string): string {
  let res = escapeHtml(text)

  // Inline code: `code`
  res = res.replace(/`([^`]+)`/g, '<code class="doc-inline-code">$1</code>')

  // Bold: **text** or __text__
  res = res.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  res = res.replace(/__([^_]+)__/g, '<strong>$1</strong>')

  // Italic: *text* or _text_
  res = res.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, '<em>$1</em>')
  res = res.replace(/(?<!_)_([^_]+)_(?!_)/g, '<em>$1</em>')

  return res
}

/**
 * Downloads the given text content as a .md file.
 */
export function downloadMarkdownFile(content: string, filename?: string): void {
  if (!content) return
  const safeName = (filename || 'documento')
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, '_')
    .slice(0, 40)
  const finalFilename = safeName.endsWith('.md') ? safeName : `${safeName}_${Date.now()}.md`
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = finalFilename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

/**
 * Generates and triggers clean print-to-PDF with document styles.
 */
export function exportDocumentToPdf(markdown: string, title?: string): void {
  if (!markdown) return
  const docTitle = title || extractDocumentTitle(markdown, 'Documento Técnico')
  const htmlContent = renderMarkdownToHtml(markdown)

  const printWindow = window.open('', '_blank')
  if (!printWindow) {
    window.print()
    return
  }

  printWindow.document.write(`
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <title>${escapeHtml(docTitle)}</title>
  <style>
    @page {
      margin: 20mm;
      size: A4;
    }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      color: #1a202c;
      background: #ffffff;
      line-height: 1.65;
      padding: 24px;
      margin: 0;
      font-size: 13.5px;
    }
    .doc-h1 {
      font-size: 24px;
      font-weight: 800;
      color: #0f172a;
      border-bottom: 2px solid #0f172a;
      padding-bottom: 10px;
      margin-top: 0;
      margin-bottom: 20px;
    }
    .doc-h2 {
      font-size: 18px;
      font-weight: 700;
      color: #1e293b;
      border-bottom: 1px solid #cbd5e1;
      padding-bottom: 6px;
      margin-top: 28px;
      margin-bottom: 12px;
    }
    .doc-h3 {
      font-size: 15px;
      font-weight: 600;
      color: #334155;
      margin-top: 20px;
      margin-bottom: 8px;
    }
    .doc-p {
      margin-top: 0;
      margin-bottom: 12px;
      text-align: justify;
    }
    .doc-ul, .doc-ol {
      margin-top: 4px;
      margin-bottom: 14px;
      padding-left: 24px;
    }
    li {
      margin-bottom: 4px;
    }
    .doc-code-block {
      background: #f1f5f9;
      border: 1px solid #e2e8f0;
      border-radius: 6px;
      padding: 12px 14px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 12px;
      overflow-x: auto;
      margin: 14px 0;
      white-space: pre-wrap;
    }
    .doc-inline-code {
      background: #f1f5f9;
      border: 1px solid #e2e8f0;
      padding: 2px 5px;
      border-radius: 4px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 12px;
      color: #0f172a;
    }
    .doc-blockquote {
      border-left: 3px solid #64748b;
      margin: 14px 0;
      padding-left: 14px;
      color: #475569;
      font-style: italic;
    }
    .doc-table {
      border-collapse: collapse;
      width: 100%;
      margin: 16px 0;
      font-size: 13px;
    }
    .doc-table th, .doc-table td {
      border: 1px solid #cbd5e1;
      padding: 8px 12px;
      text-align: left;
    }
    .doc-table th {
      background: #f8fafc;
      font-weight: 600;
      color: #0f172a;
    }
    .doc-hr {
      border: 0;
      border-top: 1px solid #e2e8f0;
      margin: 24px 0;
    }
    .doc-footer {
      margin-top: 40px;
      padding-top: 12px;
      border-top: 1px solid #e2e8f0;
      font-size: 11px;
      color: #64748b;
      display: flex;
      justify-content: space-between;
    }
    @media print {
      body { padding: 0; }
    }
  </style>
</head>
<body>
  <main>${htmlContent}</main>
  <div class="doc-footer">
    <span>Documentación generada por Atenea AI (Calíope)</span>
    <span>${new Date().toLocaleDateString('es-ES')}</span>
  </div>
  <script>
    window.onload = function() {
      window.print();
    };
  </script>
</body>
</html>
`)
  printWindow.document.close()
}
