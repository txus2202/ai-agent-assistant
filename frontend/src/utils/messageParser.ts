export interface MessageBlock {
  type: 'text' | 'mermaid'
  content: string
}

const MERMAID_REGEX = /```(?:mermaid|diagram)[^\n`]*\n([^`]+)```/gi

/**
 * Parses message markdown content into a sequential list of text blocks and
 * raw Mermaid.js diagram blocks for specialized rendering.
 */
export function parseMessageContent(rawContent: string): MessageBlock[] {
  if (!rawContent?.trim()) {
    return []
  }

  const blocks: MessageBlock[] = []
  let lastIndex = 0
  let match: RegExpExecArray | null

  MERMAID_REGEX.lastIndex = 0

  while ((match = MERMAID_REGEX.exec(rawContent)) !== null) {
    const matchStart = match.index
    const matchEnd = MERMAID_REGEX.lastIndex

    // Extract text before diagram
    if (matchStart > lastIndex) {
      const textChunk = rawContent.slice(lastIndex, matchStart).trim()
      if (textChunk) {
        blocks.push({
          type: 'text',
          content: textChunk
        })
      }
    }

    // Extract diagram code
    const diagramCode = (match[1] || '').trim()
    if (diagramCode) {
      blocks.push({
        type: 'mermaid',
        content: diagramCode
      })
    }

    lastIndex = matchEnd
  }

  // Extract remaining trailing text
  if (lastIndex < rawContent.length) {
    const trailingText = rawContent.slice(lastIndex).trim()
    if (trailingText) {
      blocks.push({
        type: 'text',
        content: trailingText
      })
    }
  }

  return blocks
}
