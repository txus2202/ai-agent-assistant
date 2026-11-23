import { extractDocumentTitle } from './markdownRenderer'
import { parsePresentation } from './slideParser'

export interface MessageBlock {
  type: 'text' | 'mermaid' | 'code' | 'image' | 'document' | 'presentation'
  content: string
  title?: string
  language?: string
  extension?: string
  alt?: string
  slideCount?: number
}

const FENCED_CODE_REGEX = /```([a-zA-Z0-9_#+-]+)?(?:[ \t][^\n]*)?\n([\s\S]*?)```/g
const IMAGE_REGEX = /!\[([^\]]*)\]\(([^)\s]+)(?:\s+"[^"]*")?\)/g

const LANGUAGE_EXTENSION_MAP: Record<string, string> = {
  javascript: 'js',
  js: 'js',
  typescript: 'ts',
  ts: 'ts',
  vue: 'vue',
  html: 'html',
  htm: 'html',
  css: 'css',
  scss: 'scss',
  sass: 'sass',
  less: 'less',
  go: 'go',
  golang: 'go',
  python: 'py',
  py: 'py',
  java: 'java',
  kotlin: 'kt',
  kt: 'kt',
  c: 'c',
  cpp: 'cpp',
  csharp: 'cs',
  cs: 'cs',
  rust: 'rs',
  rs: 'rs',
  php: 'php',
  ruby: 'rb',
  rb: 'rb',
  swift: 'swift',
  sql: 'sql',
  shell: 'sh',
  sh: 'sh',
  bash: 'sh',
  zsh: 'sh',
  json: 'json',
  yaml: 'yaml',
  yml: 'yaml',
  xml: 'xml',
  markdown: 'md',
  md: 'md',
  dockerfile: 'dockerfile',
  docker: 'dockerfile',
  txt: 'txt',
  text: 'txt',
}

export function getLanguageExtension(language?: string): string {
  if (!language) return 'txt'
  const clean = language.toLowerCase().trim()
  return LANGUAGE_EXTENSION_MAP[clean] || clean || 'txt'
}

function parseTextAndImages(textChunk: string): MessageBlock[] {
  const result: MessageBlock[] = []
  let lastIdx = 0
  let imgMatch: RegExpExecArray | null

  IMAGE_REGEX.lastIndex = 0
  while ((imgMatch = IMAGE_REGEX.exec(textChunk)) !== null) {
    if (imgMatch.index > lastIdx) {
      const before = textChunk.slice(lastIdx, imgMatch.index).trim()
      if (before) {
        result.push({ type: 'text', content: before })
      }
    }
    const alt = imgMatch[1] || 'Imagen'
    const url = imgMatch[2] || ''
    if (url) {
      result.push({ type: 'image', content: url, alt })
    }
    lastIdx = IMAGE_REGEX.lastIndex
  }

  if (lastIdx < textChunk.length) {
    const after = textChunk.slice(lastIdx).trim()
    if (after) {
      result.push({ type: 'text', content: after })
    }
  }

  return result
}

export interface ParseOptions {
  isDocumentAgent?: boolean
  agentTools?: string[]
}

const PRESENTATION_TAGS = new Set(['presentation', 'slides', 'deck', 'slide', 'diapositiva'])
const DOCUMENT_TAGS = new Set([
  'markdown',
  'md',
  'doc',
  'document',
  'pdf',
  'report',
  'manual',
  'acta',
])

function isDocumentOnlyAgent(options?: ParseOptions): boolean {
  const tools = options?.agentTools
  if (Array.isArray(tools) && tools.length > 0) {
    return tools.includes('document_viewer') && !tools.includes('code_viewer')
  }
  return Boolean(options?.isDocumentAgent)
}

function hasExplicitSlideSignals(content: string): boolean {
  if (!/(?:^|\n)---\s*(?:\n|$)/.test(content)) {
    return false
  }
  const hasExplicitSlideHeading = /(?:^|\n)##\s+(?:slide|diapositiva)\b/i.test(content)
  const hasSlideLayoutComment = /<!--\s*(?:layout|notes):\s*(?:hero|cards|split|standard|[^-]+)-->/i.test(
    content,
  )
  return hasExplicitSlideHeading || hasSlideLayoutComment
}

function createFencedBlock(
  langRaw: string,
  codeContent: string,
  options?: ParseOptions,
): MessageBlock {
  if (langRaw === 'mermaid' || langRaw === 'diagram') {
    return {
      type: 'mermaid',
      content: codeContent,
    }
  }
  if (PRESENTATION_TAGS.has(langRaw)) {
    const parsed = parsePresentation(codeContent)
    return {
      type: 'presentation',
      content: codeContent,
      title: parsed.title,
      slideCount: parsed.slides.length,
      language: 'presentation',
      extension: 'html',
    }
  }
  if (DOCUMENT_TAGS.has(langRaw) || isDocumentOnlyAgent(options)) {
    // Only treat a markdown/doc block as a presentation if it has explicit slide headings or slide layout directives
    if (hasExplicitSlideSignals(codeContent)) {
      const parsed = parsePresentation(codeContent)
      if (parsed.slides.length >= 2) {
        return {
          type: 'presentation',
          content: codeContent,
          title: parsed.title,
          slideCount: parsed.slides.length,
          language: 'presentation',
          extension: 'html',
        }
      }
    }
    return {
      type: 'document',
      content: codeContent,
      title: extractDocumentTitle(codeContent, 'Documento Técnico'),
      language: 'markdown',
      extension: 'md',
    }
  }
  return {
    type: 'code',
    content: codeContent,
    language: langRaw || 'code',
    extension: getLanguageExtension(langRaw),
  }
}

function extractDocumentAgentEnvelope(
  rawContent: string,
  options?: ParseOptions,
): MessageBlock[] | null {
  const openFenceRegex = /(?:^|\n)```([a-zA-Z0-9_#+-]+)?(?:[ \t][^\n]*)?\n/
  const openMatch = openFenceRegex.exec(rawContent)
  if (!openMatch || openMatch.index === undefined) {
    return null
  }

  const fenceOffset = openMatch[0].startsWith('\n') ? 1 : 0
  const openFenceStart = openMatch.index + fenceOffset
  const langRaw = (openMatch[1] || '').trim().toLowerCase()
  const contentStart = openMatch.index + openMatch[0].length

  // Only treat as outer document/presentation envelope if it's a document/presentation tag,
  // or if it appears before any top-level markdown heading (# Title)
  const beforeFence = rawContent.slice(0, openFenceStart).trim()
  const hasHeadingBeforeFence = /(?:^|\n)#[ \t]+[^\n]+/.test(beforeFence)
  if (hasHeadingBeforeFence && !DOCUMENT_TAGS.has(langRaw) && !PRESENTATION_TAGS.has(langRaw)) {
    return null
  }

  // Find the LAST closing fence ``` in the message so nested code blocks inside the document are preserved
  const closeFenceRegex = /\n```[ \t]*(?:\n|$)/g
  let lastCloseMatch: RegExpExecArray | null = null
  let match: RegExpExecArray | null
  closeFenceRegex.lastIndex = contentStart
  while ((match = closeFenceRegex.exec(rawContent)) !== null) {
    lastCloseMatch = match
  }

  if (!lastCloseMatch || lastCloseMatch.index === undefined) {
    return null
  }

  const innerContent = rawContent.slice(contentStart, lastCloseMatch.index).trim()
  if (!innerContent) {
    return null
  }

  const afterFence = rawContent.slice(lastCloseMatch.index + lastCloseMatch[0].length).trim()
  const result: MessageBlock[] = []

  if (beforeFence) {
    result.push(...parseTextAndImages(beforeFence))
  }
  result.push(createFencedBlock(langRaw || 'markdown', innerContent, options))
  if (afterFence) {
    result.push(...parseTextAndImages(afterFence))
  }
  return result
}

function handleDocumentAgentFallback(rawContent: string): MessageBlock[] | null {
  const matchHeading = /(?:^|\n)(#[ \t]+[^\n]+)/.exec(rawContent)
  if (matchHeading?.index === undefined) {
    return null
  }
  const headingPos = matchHeading.index + (matchHeading[0].startsWith('\n') ? 1 : 0)
  const preamble = rawContent.slice(0, headingPos).trim()
  const docContent = rawContent.slice(headingPos).trim()
  if (!docContent) {
    return null
  }
  const result: MessageBlock[] = []
  if (preamble) {
    result.push(...parseTextAndImages(preamble))
  }

  // Check if raw document contains explicit slide signals
  if (hasExplicitSlideSignals(docContent)) {
    const parsed = parsePresentation(docContent)
    if (parsed.slides.length >= 2) {
      result.push({
        type: 'presentation',
        content: docContent,
        title: parsed.title,
        slideCount: parsed.slides.length,
        language: 'presentation',
        extension: 'html'
      })
      return result
    }
  }

  result.push({
    type: 'document',
    content: docContent,
    title: extractDocumentTitle(docContent, 'Documento Técnico'),
    language: 'markdown',
    extension: 'md'
  })
  return result
}

function extractFencedBlocksAndText(rawContent: string, options?: ParseOptions): MessageBlock[] {
  const blocks: MessageBlock[] = []
  let lastIndex = 0
  let match: RegExpExecArray | null

  FENCED_CODE_REGEX.lastIndex = 0

  while ((match = FENCED_CODE_REGEX.exec(rawContent)) !== null) {
    const matchStart = match.index
    const matchEnd = FENCED_CODE_REGEX.lastIndex

    // Extract text before code block
    if (matchStart > lastIndex) {
      const textChunk = rawContent.slice(lastIndex, matchStart).trim()
      if (textChunk) {
        blocks.push(...parseTextAndImages(textChunk))
      }
    }

    const langRaw = (match[1] || '').trim().toLowerCase()
    const codeContent = (match[2] || '').trim()

    if (codeContent) {
      blocks.push(createFencedBlock(langRaw, codeContent, options))
    }

    lastIndex = matchEnd
  }

  // Extract remaining trailing text/images
  if (lastIndex < rawContent.length) {
    const trailingText = rawContent.slice(lastIndex).trim()
    if (trailingText) {
      blocks.push(...parseTextAndImages(trailingText))
    }
  }

  return blocks
}

/**
 * Parses message markdown content into a sequential list of text blocks,
 * Mermaid diagram blocks, fenced code blocks, documents, and images for specialized tool rendering.
 */
export function parseMessageContent(rawContent: string, options?: ParseOptions): MessageBlock[] {
  if (!rawContent?.trim()) {
    return []
  }

  if (isDocumentOnlyAgent(options)) {
    const envelopeBlocks = extractDocumentAgentEnvelope(rawContent, options)
    if (envelopeBlocks) {
      return envelopeBlocks
    }
    const fallbackResult = handleDocumentAgentFallback(rawContent)
    if (fallbackResult) {
      return fallbackResult
    }
  }

  const blocks = extractFencedBlocksAndText(rawContent, options)

  // Fallback for document agents (e.g. Calíope) emitting raw markdown without fenced code blocks
  if (options?.isDocumentAgent && !blocks.some((b) => b.type === 'document' || b.type === 'code')) {
    const fallbackResult = handleDocumentAgentFallback(rawContent)
    if (fallbackResult) {
      return fallbackResult
    }
  }

  return blocks
}
