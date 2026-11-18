/**
 * Utility for sanitizing agent text before Kokoro TTS / Web Audio speech synthesis.
 * Strips technical tools (code blocks, Mermaid diagrams, Markdown documents, image tags and directives)
 * and agent/role header prefixes so only conversational speech is read aloud.
 */

// Matches any fenced code/document/diagram block (```lang ... ``` or ``` ... ```)
const FENCED_TOOL_REGEX = /```[^\n`]*\n[\s\S]*?```/gi
// Matches unclosed trailing code/document block (e.g., during streaming)
const UNCLOSED_FENCE_REGEX = /```[^`]*$/i
// Matches image generation directives
const IMAGE_DIRECTIVE_REGEX = /(?:\[GENERATE_IMAGE:[^\]]*\]|<!--\s*generate_image:[\s\S]*?-->)/gi
// Matches Markdown images ![alt](url)
const IMAGE_TAG_REGEX = /!\[[^\]]*\]\([^)]+\)/g
// Matches bracketed agent prefixes like "[nl_interpreter] "
const BRACKET_PREFIX_REGEX = /^\[[\w\s.-]+\]\s*/i
// Matches single-token agent headings like "## Hermes\n" or "## the_judge\n" without touching numbered sections ("## 1. ...")
const SINGLE_TOKEN_HEADER_REGEX = /^##\s+(?:[a-záéíóúüñ_][a-záéíóúüñ0-9_-]{1,31})\s*\n+/i

function escapeRegexLiteral(value: string): string {
  return value.replaceAll(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

export function stripAgentHeaderPrefixes(
  rawContent: string,
  knownAgentNames?: Iterable<string>
): string {
  if (!rawContent) return ''
  let clean = rawContent.trim()

  const dynamicNames = new Set<string>(['Interpretation'])
  if (knownAgentNames) {
    for (const candidate of knownAgentNames) {
      const trimmed = candidate?.trim()
      if (trimmed) {
        dynamicNames.add(trimmed)
      }
    }
  }
  const escapedAlternation = Array.from(dynamicNames).map(escapeRegexLiteral).join('|')
  const knownHeaderRegex = new RegExp(`^##\\s+(?:${escapedAlternation})\\s*\\n+`, 'i')

  let changed = true
  while (changed) {
    changed = false
    if (BRACKET_PREFIX_REGEX.test(clean)) {
      clean = clean.replace(BRACKET_PREFIX_REGEX, '').trim()
      changed = true
    }
    if (knownHeaderRegex.test(clean)) {
      clean = clean.replace(knownHeaderRegex, '').trim()
      changed = true
    } else if (SINGLE_TOKEN_HEADER_REGEX.test(clean)) {
      clean = clean.replace(SINGLE_TOKEN_HEADER_REGEX, '').trim()
      changed = true
    }
  }
  return clean
}

export function getToolSpokenFallback(fenceType: string): string {
  const lower = fenceType.toLowerCase()
  if (/mermaid|diagram/.test(lower)) {
    return 'He generado el diagrama arquitectónico en pantalla.'
  }
  if (/markdown|md|doc/.test(lower)) {
    return 'He generado el documento técnico en pantalla.'
  }
  return 'He generado el código en pantalla.'
}

export function findSentenceSplitIndex(buffer: string): number {
  const terminalMatch = /[.!?\n]/.exec(buffer)
  if (terminalMatch) {
    return terminalMatch.index
  }
  if (buffer.length >= 20) {
    const clauseMatch = /[,:;]/.exec(buffer.slice(20))
    if (clauseMatch) {
      return 20 + clauseMatch.index
    }
  }
  return -1
}

export function cleanTextForTts(
  text: string,
  options?: { agentNames?: Iterable<string> }
): string {
  if (!text?.trim()) {
    return ''
  }

  // Detect tool presence before stripping
  const hasMermaid = /```(?:mermaid|diagram)/i.test(text)
  const hasDocument = /```(?:markdown|md|doc)/i.test(text)
  const hasCode = /```/i.test(text) && !hasMermaid && !hasDocument
  const hasImage = IMAGE_TAG_REGEX.test(text) || IMAGE_DIRECTIVE_REGEX.test(text)

  // Strip all tool blocks (code, diagrams, documents, image directives, markdown images)
  const textWithoutTools = text
    .replace(FENCED_TOOL_REGEX, '')
    .replace(UNCLOSED_FENCE_REGEX, '')
    .replace(IMAGE_DIRECTIVE_REGEX, '')
    .replace(IMAGE_TAG_REGEX, '')
    .trim()

  // If the message was purely a tool or deliverable, provide a natural voice fallback
  if (!textWithoutTools) {
    if (hasMermaid) {
      return 'He generado el diagrama arquitectónico en pantalla.'
    }
    if (hasDocument) {
      return 'He generado el documento técnico en pantalla.'
    }
    if (hasCode) {
      return 'He generado el código en pantalla.'
    }
    if (hasImage) {
      return 'He generado la imagen en pantalla.'
    }
    return ''
  }

  // Strip leading agent bracket tags or initial headers if present
  const cleanTtsText = stripAgentHeaderPrefixes(textWithoutTools, options?.agentNames)

  // Clean Markdown formatting:
  // 1. Markdown links [text](url) -> text
  // 2. Bold/Italic asterisks and underscores
  // 3. Header markers #
  // 4. Inline code backticks
  return cleanTtsText
    .replace(/\[([^[\]]+)\]\(([^()]+)\)/g, '$1')
    .replace(/[*#`_]/g, '')
    .replace(/\n{2,}/g, '\n')
    .trim()
}

/**
 * Splits sanitized text into TTS clauses/sentences based on punctuation:
 * terminators (. ! ? \n) and clause delimiters (, ; :) when clause length is sufficient.
 * Ensures the first chunk is short and actionable so Time-To-First-Audio is < 300-400ms.
 */
export function splitTextIntoTtsChunks(text: string): string[] {
  if (!text?.trim()) return []

  const clean = text.trim()
  // Split matching sequences of characters ending with terminal (. ! ? \n) or clause (, ; :) punctuation
  const rawParts = clean.match(/[^.!?\n,:;]+[.!?\n,:;]*/g) || [clean]

  const chunks: string[] = []
  let current = ''

  for (const part of rawParts) {
    const trimmed = part.trim()
    if (!trimmed) continue

    if (!current) {
      current = trimmed
    } else if (current.length < 20) {
      // If current chunk is still very short (under 20 characters), combine to avoid tiny unnatural fragments (e.g., "Sí,")
      current += ' ' + trimmed
    } else {
      chunks.push(current)
      current = trimmed
    }

    // If current ends with a terminal punctuation mark (. ! ? \n) or is a decent length clause ending in comma/semicolon/colon, push it
    if (/[.!?\n]$/.test(current) || (current.length >= 25 && /[,:;]$/.test(current))) {
      chunks.push(current)
      current = ''
    }
  }

  if (current.trim()) {
    chunks.push(current.trim())
  }

  return chunks.filter(c => c.length > 0)
}
