import { extractDocumentTitle } from './markdownRenderer'

export interface MessageBlock {
  type: 'text' | 'mermaid' | 'code' | 'image' | 'document'
  content: string
  title?: string
  language?: string
  extension?: string
  alt?: string
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
}

function createFencedBlock(langRaw: string, codeContent: string): MessageBlock {
  if (langRaw === 'mermaid' || langRaw === 'diagram') {
    return {
      type: 'mermaid',
      content: codeContent
    }
  }
  if (['markdown', 'md', 'doc', 'document'].includes(langRaw)) {
    return {
      type: 'document',
      content: codeContent,
      title: extractDocumentTitle(codeContent, 'Documento Técnico'),
      language: 'markdown',
      extension: 'md'
    }
  }
  return {
    type: 'code',
    content: codeContent,
    language: langRaw || 'code',
    extension: getLanguageExtension(langRaw)
  }
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
  result.push({
    type: 'document',
    content: docContent,
    title: extractDocumentTitle(docContent, 'Documento Técnico'),
    language: 'markdown',
    extension: 'md'
  })
  return result
}

function extractFencedBlocksAndText(rawContent: string): MessageBlock[] {
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
      blocks.push(createFencedBlock(langRaw, codeContent))
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

  const blocks = extractFencedBlocksAndText(rawContent)

  // Fallback for document agents (e.g. Calíope) emitting raw markdown without fenced code blocks
  if (options?.isDocumentAgent && !blocks.some(b => b.type === 'document' || b.type === 'code')) {
    const fallbackResult = handleDocumentAgentFallback(rawContent)
    if (fallbackResult) {
      return fallbackResult
    }
  }

  return blocks
}
