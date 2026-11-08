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

  it('removes html code blocks from Fidias and speaks only conversational text', () => {
    const input = `Entiendo perfectamente tu requerimiento visual. He preparado la maquetación solicitada:
\`\`\`html
<!DOCTYPE html>
<html lang="es">
<head>
  <style>
    body { background: #000; color: #fff; }
  </style>
</head>
<body>
  <div class="carousel">Productos</div>
</body>
</html>
\`\`\`
¿Qué te parece la estructura propuesta?`

    const result = cleanTextForTts(input)
    expect(result).not.toContain('<!DOCTYPE html>')
    expect(result).not.toContain('background')
    expect(result).not.toContain('<style>')
    expect(result).toContain('Entiendo perfectamente tu requerimiento visual. He preparado la maquetación solicitada:')
    expect(result).toContain('¿Qué te parece la estructura propuesta?')
  })

  it('provides a natural spoken fallback if the message only contains an html/code block', () => {
    const input = `\`\`\`html
<!DOCTYPE html>
<html><body><h1>Demo</h1></body></html>
\`\`\``

    const result = cleanTextForTts(input)
    expect(result).toBe('He generado el código en pantalla.')
  })

  it('removes document blocks from Caliope and provides document fallback', () => {
    const inputWithIntro = `A continuación presento la documentación técnica:
\`\`\`markdown
# Manual de Arquitectura
## 1. Introducción
Este es el contenido formal para exportación.
\`\`\`
Puedes descargarlo en los botones superiores.`

    const resultWithIntro = cleanTextForTts(inputWithIntro)
    expect(resultWithIntro).not.toContain('Manual de Arquitectura')
    expect(resultWithIntro).not.toContain('Introducción')
    expect(resultWithIntro).toContain('A continuación presento la documentación técnica:')
    expect(resultWithIntro).toContain('Puedes descargarlo en los botones superiores.')

    const inputOnlyDoc = `\`\`\`markdown
# Acta de Reunión
Detalle de participantes y acuerdos.
\`\`\``
    expect(cleanTextForTts(inputOnlyDoc)).toBe('He generado el documento técnico en pantalla.')
  })

  it('removes image tags and image generation directives from text', () => {
    const input = `Propuesta de diseño:
[GENERATE_IMAGE: Futuristic dark cybersecurity dashboard with cyan neon glowing cards, 8k]
![Dashboard](/api/images/fidias_123.png)
He seleccionado una paleta con alto contraste.`

    const result = cleanTextForTts(input)
    expect(result).not.toContain('GENERATE_IMAGE')
    expect(result).not.toContain('/api/images/fidias_123.png')
    expect(result).toContain('Propuesta de diseño:')
    expect(result).toContain('He seleccionado una paleta con alto contraste.')

    const inputOnlyImg = '![Logo](/api/images/fidias_logo.png)'
    expect(cleanTextForTts(inputOnlyImg)).toBe('He generado la imagen en pantalla.')
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
