/**
 * Utility for sanitizing agent text before Kokoro TTS / Web Audio speech synthesis.
 * Strips technical tools (code blocks, Mermaid diagrams, Markdown documents, image tags and directives)
 * to ensure that only conversational speech is read aloud and no tool syntax/code is ever spoken.
 */

// Matches any fenced code/document/diagram block (```lang ... ``` or ``` ... ```)
const FENCED_TOOL_REGEX = /```[^\n`]*\n[\s\S]*?```/gi
// Matches unclosed trailing code/document block (e.g., during streaming)
const UNCLOSED_FENCE_REGEX = /```[\s\S]*$/gi
// Matches image generation directives
const IMAGE_DIRECTIVE_REGEX = /(?:\[GENERATE_IMAGE:[^\]]*\]|<!--\s*generate_image:[\s\S]*?-->)/gi
// Matches Markdown images ![alt](url)
const IMAGE_TAG_REGEX = /!\[[^\]]*\]\([^)]+\)/g

export function cleanTextForTts(text: string): string {
  if (!text?.trim()) {
    return ''
  }

  // Detect tool presence before stripping
  const hasMermaid = /```(?:mermaid|diagram)/i.test(text)
  const hasDocument = /```(?:markdown|md|doc)/i.test(text)
  const hasCode = /```(?:html|js|javascript|ts|typescript|css|py|python|go|golang|java|json|bash|sh|sql|vue|jsx|tsx|cpp|c|rust|php|yaml|yml)/i.test(text) || (/```/i.test(text) && !hasMermaid && !hasDocument)
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
  const cleanTtsText = textWithoutTools
    .replace(/^\[[\w\s.-]+\]\s*/i, '')
    .replace(/^##\s+(?:Interpretation|Ícaro|Icaro|Hermes|Hestia|Sphinx|the_judge|nl_interpreter|innovator_architect|senior_architect|atenea|supervisor|fidias|fídias|dedalo|dédalo|caliope|calíope)\s*\n+/i, '')
    .trim()

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
