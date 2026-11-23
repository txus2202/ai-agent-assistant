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

  it('parses code blocks with language and proper file extension', () => {
    const text = `Aquí está el código en Go:
\`\`\`go
package main

import "fmt"

func main() {
    fmt.Println("Hello Olimpo")
}
\`\`\`
Y este es el componente en Vue:
\`\`\`vue
<template><div>Dédalo</div></template>
\`\`\``

    const blocks = parseMessageContent(text)
    expect(blocks).toHaveLength(4)
    expect(blocks[0]!.type).toBe('text')
    expect(blocks[1]!.type).toBe('code')
    expect(blocks[1]!.language).toBe('go')
    expect(blocks[1]!.extension).toBe('go')
    expect(blocks[1]!.content).toContain('package main')

    expect(blocks[2]!.type).toBe('text')
    expect(blocks[3]!.type).toBe('code')
    expect(blocks[3]!.language).toBe('vue')
    expect(blocks[3]!.extension).toBe('vue')
  })

  it('parses markdown images properly', () => {
    const text = `Diseño de Fidias:
![Landing Mockup](https://example.com/mockup.png)
¿Qué te parece?`

    const blocks = parseMessageContent(text)
    expect(blocks).toHaveLength(3)
    expect(blocks[0]!.type).toBe('text')
    expect(blocks[1]!.type).toBe('image')
    expect(blocks[1]!.alt).toBe('Landing Mockup')
    expect(blocks[1]!.content).toBe('https://example.com/mockup.png')
    expect(blocks[2]!.type).toBe('text')
  })

  it('parses fenced markdown block as document type with extracted title', () => {
    const text = `Documentación de Calíope:
\`\`\`markdown
# Especificación del Sistema
## 1. Alcance
Contenido de la especificación técnica.
\`\`\`
Fin del documento.`

    const blocks = parseMessageContent(text)
    expect(blocks).toHaveLength(3)
    expect(blocks[0]!.type).toBe('text')
    expect(blocks[1]!.type).toBe('document')
    expect(blocks[1]!.title).toBe('Especificación del Sistema')
    expect(blocks[1]!.content).toContain('## 1. Alcance')
    expect(blocks[2]!.type).toBe('text')
  })

  it('separates preamble and document block for document agents when raw markdown is emitted without backticks', () => {
    const text = `Soy Calíope, redactora elocuente. A continuación presento la documentación:

# Proyecto Agentes
## 1. Resumen
Este es el documento oficial sin bloques delimitados.`

    const blocks = parseMessageContent(text, { isDocumentAgent: true })
    expect(blocks).toHaveLength(2)
    expect(blocks[0]!.type).toBe('text')
    expect(blocks[0]!.content).toBe('Soy Calíope, redactora elocuente. A continuación presento la documentación:')
    expect(blocks[1]!.type).toBe('document')
    expect(blocks[1]!.title).toBe('Proyecto Agentes')
    expect(blocks[1]!.content).toBe('# Proyecto Agentes\n## 1. Resumen\nEste es el documento oficial sin bloques delimitados.')
  })

  it('parses fenced presentation and slides blocks into presentation type', () => {
    const text = `Aquí tienes la presentación solicitada:
\`\`\`presentation
# Propuesta de Arquitectura
---
## Slide 1: Resumen
- Punto 1
- Punto 2
---
## Slide 2: Stack
- Vue
- FastAPI
\`\`\`
¿Te parece adecuada?`

    const blocks = parseMessageContent(text)
    expect(blocks).toHaveLength(3)
    expect(blocks[0]!.type).toBe('text')
    expect(blocks[1]!.type).toBe('presentation')
    expect(blocks[1]!.title).toBe('Propuesta de Arquitectura')
    expect(blocks[1]!.slideCount).toBe(2)
    expect(blocks[2]!.type).toBe('text')
  })

  it('identifies presentations with slides language tag or markdown containing multiple slide dividers', () => {
    const text = `\`\`\`slides
# Demo Slides
---
## Diapositiva 1
- Contenido
\`\`\``

    const blocks = parseMessageContent(text)
    expect(blocks).toHaveLength(1)
    expect(blocks[0]!.type).toBe('presentation')
    expect(blocks[0]!.title).toBe('Demo Slides')
    expect(blocks[0]!.slideCount).toBe(1)
  })

  it('parses ```pdf and ```report fenced blocks as document type', () => {
    const text = `Aquí tienes el manual en PDF solicitado:
\`\`\`pdf
# Manual de Despliegue y Operaciones
## 1. Introducción
Este manual describe el procedimiento paso a paso.
\`\`\``

    const blocks = parseMessageContent(text, { isDocumentAgent: true, agentTools: ['document_viewer', 'presentation_viewer'] })
    expect(blocks).toHaveLength(2)
    expect(blocks[0]!.type).toBe('text')
    expect(blocks[1]!.type).toBe('document')
    expect(blocks[1]!.title).toBe('Manual de Despliegue y Operaciones')
    expect(blocks[1]!.content).toContain('## 1. Introducción')
  })

  it('keeps nested code fences inside a document block intact without emitting code blocks when agent only has document_viewer', () => {
    const text = `Aquí tienes el manual técnico:
\`\`\`markdown
# Manual de Configuración
## 1. Variables de Entorno
Ejecuta el siguiente comando en terminal:
\`\`\`bash
docker compose up -d --build
\`\`\`
## 2. Conclusión
El sistema quedará operativo.
\`\`\``

    const blocks = parseMessageContent(text, {
      isDocumentAgent: true,
      agentTools: ['document_viewer', 'presentation_viewer']
    })
    expect(blocks).toHaveLength(2)
    expect(blocks[0]!.type).toBe('text')
    expect(blocks[0]!.content).toBe('Aquí tienes el manual técnico:')
    expect(blocks[1]!.type).toBe('document')
    expect(blocks[1]!.title).toBe('Manual de Configuración')
    expect(blocks[1]!.content).toContain('```bash\ndocker compose up -d --build\n```')
    expect(blocks[1]!.content).toContain('## 2. Conclusión')
    expect(blocks.some(b => b.type === 'code')).toBe(false)
  })

  it('treats raw markdown document containing embedded code blocks as a single document when agent has document_viewer and not code_viewer', () => {
    const text = `Claro, aquí tienes el reporte en PDF:

# Reporte de Seguridad
## 1. Script de Auditoría
\`\`\`python
def audit():
    return True
\`\`\`
## 2. Resultado
Todo en orden.`

    const blocks = parseMessageContent(text, {
      isDocumentAgent: true,
      agentTools: ['document_viewer', 'presentation_viewer']
    })
    expect(blocks).toHaveLength(2)
    expect(blocks[0]!.type).toBe('text')
    expect(blocks[0]!.content).toBe('Claro, aquí tienes el reporte en PDF:')
    expect(blocks[1]!.type).toBe('document')
    expect(blocks[1]!.title).toBe('Reporte de Seguridad')
    expect(blocks[1]!.content).toContain('```python')
    expect(blocks[1]!.content).toContain('## 2. Resultado')
    expect(blocks.some(b => b.type === 'code')).toBe(false)
  })

  it('never emits code block for an agent with document_viewer and without code_viewer even if fenced with an arbitrary tag', () => {
    const text = `Aquí tienes el documento solicitado:
\`\`\`txt
# Acta de Reunión: Arquitectura
- Fecha: Hoy
- Acuerdos: Usar PostgreSQL
\`\`\``

    const blocks = parseMessageContent(text, {
      isDocumentAgent: true,
      agentTools: ['document_viewer']
    })
    expect(blocks).toHaveLength(2)
    expect(blocks[1]!.type).toBe('document')
    expect(blocks[1]!.title).toBe('Acta de Reunión: Arquitectura')
    expect(blocks.some(b => b.type === 'code')).toBe(false)
  })

  it('does NOT classify a markdown document or manual with horizontal rules (---) or tables as a presentation unless it has explicit slide headers or layout directives', () => {
    const text = `Aquí tienes el documento solicitado:
\`\`\`markdown
# Manual de Arquitectura y Operaciones

---

## 1. Introducción
Este manual técnico detalla la arquitectura del sistema Atenea y sus componentes principales.

| Componente | Puerto | Descripción |
|---|---|---|
| Backend | 8000 | API FastAPI |
| Frontend | 5173 | SPA Vue 3 |

---

## 2. Procedimiento de Despliegue
Para desplegar la solución en producción sigue estos pasos detallados.
\`\`\``

    const blocks = parseMessageContent(text, {
      isDocumentAgent: true,
      agentTools: ['document_viewer', 'presentation_viewer']
    })
    expect(blocks).toHaveLength(2)
    expect(blocks[0]!.type).toBe('text')
    expect(blocks[1]!.type).toBe('document')
    expect(blocks[1]!.title).toBe('Manual de Arquitectura y Operaciones')
  })

  it('does NOT classify raw markdown document with horizontal rules (---) as a presentation in fallback mode', () => {
    const text = `Aquí tienes el reporte:

# Reporte Técnico de Auditoría
---
## 1. Alcance
Descripción detallada del alcance de la auditoría.
---
## 2. Conclusiones
El sistema cumple con los requisitos.`

    const blocks = parseMessageContent(text, {
      isDocumentAgent: true,
      agentTools: ['document_viewer', 'presentation_viewer']
    })
    expect(blocks).toHaveLength(2)
    expect(blocks[1]!.type).toBe('document')
    expect(blocks[1]!.title).toBe('Reporte Técnico de Auditoría')
  })
})
