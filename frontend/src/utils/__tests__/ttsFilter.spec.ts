import { describe, it, expect } from 'vitest'
import { cleanTextForTts, splitTextIntoTtsChunks } from '../ttsFilter'

describe('cleanTextForTts', () => {
  it('removes mermaid diagram code blocks and keeps introductory and trailing text', () => {
    const input = `Aquí tienes el diseño del sistema:
\`\`\`mermaid
flowchart TD
  A[Cliente] --> B[API Gateway]
  B --> C[Servicio de Autenticación]
\`\`\`
¿Te parece adecuada esta distribución?`

    const result = cleanTextForTts(input)
    expect(result).not.toContain('flowchart')
    expect(result).not.toContain('Cliente')
    expect(result).not.toContain('API Gateway')
    expect(result).toContain('Aquí tienes el diseño del sistema:')
    expect(result).toContain('¿Te parece adecuada esta distribución?')
  })

  it('provides a natural spoken fallback if the message only contains a mermaid diagram', () => {
    const input = `\`\`\`mermaid
flowchart LR
  Front --> Back
\`\`\``

    const result = cleanTextForTts(input)
    expect(result).toBe('He generado el diagrama arquitectónico en pantalla.')
  })

  it('handles multiple mermaid code blocks in the same message', () => {
    const input = `Primer flujo:
\`\`\`mermaid
flowchart TD
  A --> B
\`\`\`
Segundo flujo:
\`\`\`mermaid
sequenceDiagram
  Client ->> Server: Request
\`\`\`
Todos los diagramas han sido generados.`

    const result = cleanTextForTts(input)
    expect(result).not.toContain('sequenceDiagram')
    expect(result).not.toContain('flowchart')
    expect(result).toContain('Primer flujo:')
    expect(result).toContain('Segundo flujo:')
    expect(result).toContain('Todos los diagramas han sido generados.')
  })

  it('cleans markdown symbols from text for smooth speech synthesis', () => {
    const input = 'Revisa la **arquitectura** en el [enlace](http://example.com) y confirma los _requisitos_.'
    const result = cleanTextForTts(input)
    expect(result).toBe('Revisa la arquitectura en el enlace y confirma los requisitos.')
  })

  it('returns empty string if input is empty or only whitespace', () => {
    expect(cleanTextForTts('')).toBe('')
    expect(cleanTextForTts('   \n  ')).toBe('')
  })
})

describe('splitTextIntoTtsChunks', () => {
  it('returns empty array for empty or whitespace text', () => {
    expect(splitTextIntoTtsChunks('')).toEqual([])
    expect(splitTextIntoTtsChunks('   ')).toEqual([])
  })

  it('splits text into sentences by terminal punctuation', () => {
    const input = 'Primera frase. Segunda frase! ¿Tercera frase?'
    const result = splitTextIntoTtsChunks(input)
    expect(result).toHaveLength(3)
    expect(result[0]).toBe('Primera frase.')
    expect(result[1]).toBe('Segunda frase!')
    expect(result[2]).toBe('¿Tercera frase?')
  })

  it('splits long sentences with commas into smaller clauses for low-latency streaming', () => {
    const input = 'Entendido, estoy comprobando todos los servicios del clúster, y verificando la memoria.'
    const result = splitTextIntoTtsChunks(input)
    expect(result.length).toBeGreaterThan(1)
    expect(result[0]).toContain('Entendido, estoy comprobando todos los servicios del clúster,')
    expect(result[result.length - 1]).toContain('y verificando la memoria.')
  })
})
