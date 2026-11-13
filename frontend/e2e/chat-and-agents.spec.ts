import { test, expect } from '@playwright/test'
import { setupMockBackend } from './helpers/mockBackend'

test.describe('Chat, Agents and HITL Interaction', () => {
  test('should load main view with all system components', async ({ page }) => {
    await setupMockBackend(page)

    await page.goto('/')

    // Header and branding
    await expect(page.locator('[data-test="header-left-section"]')).toBeVisible()
    await expect(page.locator('[data-test="header-right-section"]')).toBeVisible()

    // Chat panel and controls
    await expect(page.locator('textarea[placeholder*="consulta"]')).toBeVisible()
    await expect(page.locator('[data-test="chat-send-btn"]')).toBeVisible()
    await expect(page.locator('[data-test="agent-dropdown-btn"]')).toBeVisible()
  })

  test('should allow selecting a specialist agent from dropdown', async ({ page }) => {
    await setupMockBackend(page)

    await page.goto('/')

    const dropdownBtn = page.locator('[data-test="agent-dropdown-btn"]')
    await expect(dropdownBtn).toBeVisible()
    await dropdownBtn.click()

    // Agent options
    const options = page.locator('[data-test="agent-option"]')
    await expect(options.first()).toBeVisible()
    const count = await options.count()
    expect(count).toBeGreaterThanOrEqual(2)

    // Select the "Arquitecto" agent
    const architectOption = options.filter({ hasText: 'Arquitecto' })
    await architectOption.click()

    // The button reflects selected agent
    await expect(dropdownBtn).toContainText('Arquitecto')
  })

  test('should send user message and receive streaming assistant response via WebSocket', async ({
    page,
  }) => {
    const wsController = await setupMockBackend(page)

    await page.goto('/')
    await expect(page.locator('[data-test="header-left-section"]')).toBeVisible()

    const input = page.locator('textarea[placeholder*="consulta"]')
    await input.fill('¿Cuál es la estrategia recomendada para desacoplar servicios?')

    // Send user message
    const sendBtn = page.locator('[data-test="chat-send-btn"]')
    await sendBtn.click()

    // User message bubble appears in chat
    await expect(page.locator('text=¿Cuál es la estrategia recomendada para desacoplar servicios?')).toBeVisible()

    // Backend simulates assistant WebSocket stream
    await wsController.sendStreamingAssistantMessage(
      'Recomiendo usar Event-Driven Architecture con Apache Kafka o RabbitMQ para desacoplar productores y consumidores.',
      'architect'
    )

    // Assistant reply appears in chat
    await expect(
      page.locator('text=Recomiendo usar Event-Driven Architecture con Apache Kafka')
    ).toBeVisible()
  })

  test('should display HITL controls and allow taking an approval decision', async ({
    page,
  }) => {
    const wsController = await setupMockBackend(page)

    await page.goto('/')
    await expect(page.locator('[data-test="header-left-section"]')).toBeVisible()

    // Trigger server HITL prompt
    await wsController.sendHITLRequest('¿Autorizas el despliegue del nuevo cluster en producción?')

    // HITL card appears in chat
    const hitlCard = page.locator('[data-test="hitl-chat-card"]')
    await expect(hitlCard).toBeVisible()
    await expect(hitlCard).toContainText('Punto de Control (HITL)')

    // Decision action buttons must be present
    const approveBtn = page.locator('[data-test="hitl-approve-btn"]')
    await expect(approveBtn).toBeVisible()
    await expect(page.locator('[data-test="hitl-refine-btn"]')).toBeVisible()
    await expect(page.locator('[data-test="hitl-retry-btn"]')).toBeVisible()

    // Approve the action
    await approveBtn.click()

    // Decision dispatched and card completes/hides
    await expect(hitlCard).not.toBeVisible()
  })

  test('should show floating scroll button when chat content overflows', async ({
    page,
  }) => {
    const wsController = await setupMockBackend(page)

    await page.goto('/')
    await expect(page.locator('[data-test="header-left-section"]')).toBeVisible()

    // Send multiple long messages to force scroll overflow
    for (let i = 1; i <= 6; i++) {
      await wsController.sendStreamingAssistantMessage(
        `Mensaje de reporte número ${i}: Este es un párrafo con suficiente longitud para hacer que el historial del chat desborde el alto de la pantalla y requiera navegación por scroll en el contenedor principal. Detalle técnico del paso ${i} verificado satisfactoriamente con múltiples agentes del consejo deliberando en paralelo.`
      )
    }

    // Trigger scroll evaluation
    await page.evaluate(() => window.dispatchEvent(new Event('resize')))

    // Floating scroll toggle button must be attached in DOM
    const scrollBtn = page.locator('[data-test="chat-scroll-toggle-btn"]')
    await expect(scrollBtn).toBeAttached()
  })
})
