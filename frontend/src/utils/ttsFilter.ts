/**
 * Utility for sanitizing agent text before Kokoro TTS speech synthesis.
 * Strips technical Mermaid diagram code blocks to prevent reading code syntax aloud.
 */

const MERMAID_BLOCK_REGEX = /```(?:mermaid|diagram)[^\n`]*\n[^`]*```/gi

export function cleanTextForTts(text: string): string {
  if (!text?.trim()) {
    return ''
  }

  // Check if diagram blocks exist in the text
  const hasDiagram = MERMAID_BLOCK_REGEX.test(text)
  MERMAID_BLOCK_REGEX.lastIndex = 0

  // Strip diagram blocks
  const textWithoutDiagrams = text.replace(MERMAID_BLOCK_REGEX, '').trim()

  // If the message was purely a diagram (or only diagrams), provide an informative voice fallback
  if (!textWithoutDiagrams && hasDiagram) {
    return 'He generado el diagrama arquitectónico en pantalla.'
  }

  if (!textWithoutDiagrams) {
    return ''
  }

  // Strip leading agent bracket tags or initial headers if present
  const cleanTtsText = textWithoutDiagrams
    .replace(/^\[[\w\s.-]+\]\s*/i, '')
    .replace(/^##\s+(?:Interpretation|Ícaro|Icaro|Hermes|Hestia|Sphinx|the_judge|nl_interpreter|innovator_architect|senior_architect|atenea|supervisor)\s*\n+/i, '')
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
