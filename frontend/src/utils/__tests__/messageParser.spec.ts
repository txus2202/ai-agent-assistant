import { describe, it, expect } from 'vitest'
import { parseMessageContent } from '../messageParser'

describe('parseMessageContent', () => {
  it('returns a single text block when message has no diagram code blocks', () => {
    const text = 'Hola, soy Atenea. ¿En qué puedo ayudarte hoy?'
    const blocks = parseMessageContent(text)
    expect(blocks).toEqual([
      { type: 'text', content: text }
    ])
  })

  it('splits message with text and a mermaid block', () => {
    const text = `Aquí tienes el diagrama:
\`\`\`mermaid
flowchart TD
  A[Cliente] --> B[Servidor]
\`\`\`
¿Quieres ajustar algún detalle?`

    const blocks = parseMessageContent(text)
    expect(blocks).toHaveLength(3)
    expect(blocks[0]).toEqual({
      type: 'text',
      content: 'Aquí tienes el diagrama:'
    })
    expect(blocks[1]!.type).toBe('mermaid')
    expect(blocks[1]!.content).toBe('flowchart TD\n  A[Cliente] --> B[Servidor]')
    expect(blocks[2]).toEqual({
      type: 'text',
      content: '¿Quieres ajustar algún detalle?'
    })
  })

  it('handles message containing only a mermaid block', () => {
    const text = `\`\`\`mermaid
sequenceDiagram
  A->>B: Ping
  B-->>A: Pong
\`\`\``

    const blocks = parseMessageContent(text)
    expect(blocks).toHaveLength(1)
    expect(blocks[0]!.type).toBe('mermaid')
    expect(blocks[0]!.content).toBe('sequenceDiagram\n  A->>B: Ping\n  B-->>A: Pong')
  })

  it('handles multiple mermaid blocks in one message', () => {
    const text = `Diagrama 1:
\`\`\`mermaid
flowchart LR
  A --> B
\`\`\`
Diagrama 2:
\`\`\`mermaid
flowchart TD
  C --> D
\`\`\``

    const blocks = parseMessageContent(text)
    expect(blocks).toHaveLength(4)
    expect(blocks[0]!.type).toBe('text')
    expect(blocks[1]!.type).toBe('mermaid')
    expect(blocks[1]!.content).toBe('flowchart LR\n  A --> B')
    expect(blocks[2]!.type).toBe('text')
    expect(blocks[3]!.type).toBe('mermaid')
    expect(blocks[3]!.content).toBe('flowchart TD\n  C --> D')
  })

  it('returns empty array when content is empty', () => {
    expect(parseMessageContent('')).toEqual([])
  })
})
