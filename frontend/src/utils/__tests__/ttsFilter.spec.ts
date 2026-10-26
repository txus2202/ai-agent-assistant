import { describe, it, expect } from 'vitest'
import { cleanTextForTts } from '../ttsFilter'

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
