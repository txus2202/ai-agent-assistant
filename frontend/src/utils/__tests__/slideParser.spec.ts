import { describe, it, expect } from 'vitest'
import { parsePresentation } from '../slideParser'

describe('slideParser.ts', () => {
  it('handles empty or whitespace-only input', () => {
    const res = parsePresentation('')
    expect(res.title).toBe('Presentación')
    expect(res.slides).toHaveLength(0)
  })

  it('parses a presentation with title and multiple slides separated by ---', () => {
    const raw = `
# Arquitectura de Autenticación
---
## Resumen Ejecutivo
<!-- layout: hero -->
> Plataforma centralizada de gestión de sesiones de alta disponibilidad.
- **Decisión:** Opción Hestia-1.
- **Objetivo:** Consistencia estricta y seguridad.
<!-- notes: Enfatizar la reducción de deuda técnica. -->
---
## Stack Tecnológico
<!-- layout: cards -->
### PostgreSQL
- Base de datos primaria SSOT.
- Integridad transaccional ACID.
### Redis Cluster
- Sesiones activas en memoria.
- Latencia sub-milisegundo.
### Servicio Auth-Core
- Validación centralizada de tokens.
---
## Métricas de Rendimiento
<!-- layout: standard -->
- Latencia p99: **< 15ms**
- Throughput objetivo: **5000 req/s**
- Disponibilidad SLA: **99.99%**
`
    const res = parsePresentation(raw)

    expect(res.title).toBe('Arquitectura de Autenticación')
    expect(res.slides).toHaveLength(3)

    // Slide 1: Hero
    const s1 = res.slides[0]!
    expect(s1.index).toBe(1)
    expect(s1.title).toBe('Resumen Ejecutivo')
    expect(s1.subtitle).toBe('Plataforma centralizada de gestión de sesiones de alta disponibilidad.')
    expect(s1.layout).toBe('hero')
    expect(s1.bullets).toHaveLength(2)
    expect(s1.bullets[0]).toContain('Decisión')
    expect(s1.notes).toBe('Enfatizar la reducción de deuda técnica.')

    // Slide 2: Cards
    const s2 = res.slides[1]!
    expect(s2.index).toBe(2)
    expect(s2.title).toBe('Stack Tecnológico')
    expect(s2.layout).toBe('cards')
    expect(s2.cards).toHaveLength(3)
    expect(s2.cards[0]!.title).toBe('PostgreSQL')
    expect(s2.cards[0]!.content).toContain('Base de datos primaria SSOT.')
    expect(s2.cards[1]!.title).toBe('Redis Cluster')
    expect(s2.cards[2]!.title).toBe('Servicio Auth-Core')
    // Ensure bullets inside ### cards are NOT duplicated into slide.bullets
    expect(s2.bullets).toHaveLength(0)

    // Slide 3: Standard
    const s3 = res.slides[2]!
    expect(s3.index).toBe(3)
    expect(s3.title).toBe('Métricas de Rendimiento')
    expect(s3.layout).toBe('standard')
    expect(s3.bullets).toHaveLength(3)
    expect(s3.bullets[0]).toContain('Latencia p99')
  })

  it('automatically infers layout if not explicitly declared in html comment', () => {
    const raw = `
## Portada
> Subtítulo introductorio

---
## Módulos
### Frontend
- Vue 3 + Tailwind
### Backend
- FastAPI + Python

---
## Conclusiones
- Despliegue en Q1
- Auditoría aprobada
`
    const res = parsePresentation(raw)
    expect(res.slides).toHaveLength(3)
    expect(res.slides[0]!.layout).toBe('hero') // First slide with blockquote -> hero
    expect(res.slides[1]!.layout).toBe('cards') // Slide with ### headings -> cards
    expect(res.slides[2]!.layout).toBe('standard')
  })

  it('parses legacy format where slides are delineated only with ## Slide N', () => {
    const raw = `
# Presentación Calíope

## Slide 1: Resumen Ejecutivo
Propósito: Establecer sistema robusto.
- Punto 1
- Punto 2

## Slide 2: Stack Tecnológico
- PostgreSQL
- Redis
`
    const res = parsePresentation(raw)
    expect(res.slides).toHaveLength(2)
    expect(res.slides[0]!.title).toBe('Resumen Ejecutivo')
    expect(res.slides[1]!.title).toBe('Stack Tecnológico')
  })
})
