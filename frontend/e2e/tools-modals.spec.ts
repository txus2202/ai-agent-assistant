import { test, expect } from '@playwright/test'
import { setupMockBackend } from './helpers/mockBackend'

test.describe('Visual Tools and Modals', () => {
  test('should open and allow navigating slides in presentation modal', async ({
    page,
  }) => {
    const wsController = await setupMockBackend(page)

    await page.goto('/')

    // Dispatch markdown presentation with 3 slides
    const presentationMarkdown = `# Arquitectura de Atenea AI
---
## Diapositiva 1
> Visión General
- Coordinación multi-agente
- Supervisión continua
---
## Diapositiva 2
### Ingestion [RAG]
Indexación en ChromaDB vectorial
### Procesamiento [LLM]
Lógica distribuida con FastAPI
---
## Diapositiva 3
> Conclusión
- Despliegue seguro con Docker
`
    await wsController.sendPresentation(presentationMarkdown)

    // Presentation card appears in chat
    const presCard = page.locator('[data-test="chat-presentation-card"]')
    await expect(presCard).toBeVisible()

    // Open presentation modal
    const viewBtn = page.locator('[data-test="chat-presentation-view-btn"]')
    await viewBtn.click()

    // Modal is opened
    const modal = page.locator('[data-test="presentation-modal-backdrop"]')
    await expect(modal).toBeVisible()

    // Verify initial slide counter
    const counter = page.locator('[data-test="slide-counter"]')
    await expect(counter).toContainText('1 / 3')

    // Navigate to next slide
    const nextBtn = page.locator('[data-test="slide-next-btn"]')
    await nextBtn.click()
    await expect(counter).toContainText('2 / 3')

    // Navigate to previous slide
    const prevBtn = page.locator('[data-test="slide-prev-btn"]')
    await prevBtn.click()
    await expect(counter).toContainText('1 / 3')

    // Navigate using ArrowRight keyboard key
    await page.keyboard.press('ArrowRight')
    await expect(counter).toContainText('2 / 3')

    // Verify export download dropdown
    const downloadBtn = page.locator('[data-test="presentation-modal-download-btn"]')
    await downloadBtn.click()
    await expect(page.locator('[data-test="download-option-pptx"]')).toBeVisible()
    await expect(page.locator('[data-test="download-option-html"]')).toBeVisible()

    // Close modal via Escape key
    await page.keyboard.press('Escape')
    await expect(modal).not.toBeVisible()
  })

  test('should open Mermaid diagram viewer with zoom controls', async ({ page }) => {
    const wsController = await setupMockBackend(page)

    await page.goto('/')

    const mermaidCode = `graph TD
      A[Cliente Frontend] --> B[FastAPI Gateway]
      B --> C[ChromaDB]
      B --> D[Agente Supervisor]
    `
    await wsController.sendDiagram(mermaidCode)

    // Diagram card in chat
    const diagramCard = page.locator('[data-test="chat-diagram-card"]')
    await expect(diagramCard).toBeVisible()

    // Open diagram modal
    const viewBtn = page.locator('[data-test="chat-diagram-view-btn"]')
    await viewBtn.click()

    // Modal backdrop visible
    const modal = page.locator('[data-test="diagram-modal-backdrop"]')
    await expect(modal).toBeVisible()

    // Check zoom controls
    const zoomInBtn = page.locator('[data-test="zoom-in-btn"]')
    const zoomOutBtn = page.locator('[data-test="zoom-out-btn"]')
    const zoomResetBtn = page.locator('[data-test="zoom-reset-btn"]')

    await expect(zoomInBtn).toBeVisible()
    await expect(zoomOutBtn).toBeVisible()
    await expect(zoomResetBtn).toBeVisible()

    // Test zoom button interactions
    await zoomInBtn.click()
    await zoomResetBtn.click()

    // Close diagram modal
    const closeBtn = page.locator('[data-test="diagram-modal-close-btn"]')
    await closeBtn.click()
    await expect(modal).not.toBeVisible()
  })

  test('should open source code viewer and allow copying content', async ({
    page,
  }) => {
    const wsController = await setupMockBackend(page)

    await page.goto('/')

    const codeSnippet = 'export function calculateTotal(items: number[]): number {\n  return items.reduce((a, b) => a + b, 0)\n}'
    await wsController.sendCode(codeSnippet)

    // Code card in chat
    const codeCard = page.locator('[data-test="chat-code-card"]')
    await expect(codeCard).toBeVisible()

    // Open code modal
    const viewBtn = page.locator('[data-test="chat-code-view-btn"]')
    await viewBtn.click()

    // Code modal visible
    const modal = page.locator('[data-test="code-modal-backdrop"]')
    await expect(modal).toBeVisible()

    // Code container visible
    await expect(page.locator('[data-test="code-modal-code-container"]')).toBeVisible()

    // Close code modal
    const closeBtn = page.locator('[data-test="code-modal-close-btn"]')
    await closeBtn.click()
    await expect(modal).not.toBeVisible()
  })
})
