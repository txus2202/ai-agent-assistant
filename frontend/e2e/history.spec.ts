import { test, expect } from '@playwright/test'
import { setupMockBackend } from './helpers/mockBackend'

test.describe('Conversation History', () => {
  test('should navigate to history from header and list archived deliberations', async ({
    page,
  }) => {
    await setupMockBackend(page)

    await page.goto('/')

    // Click history button in header
    const historyBtn = page.locator('[data-test="history-btn"]')
    await expect(historyBtn).toBeVisible()
    await historyBtn.click()

    await expect(page).toHaveURL(/.*\/history/)
    await expect(page.locator('h1')).toContainText('HISTORIAL DE CONVERSACIONES')

    // Archived session cards must be rendered
    const sessionCards = page.locator('[data-test="session-card"]')
    await expect(sessionCards.first()).toBeVisible()
    const count = await sessionCards.count()
    expect(count).toBeGreaterThanOrEqual(2)
  })

  test('should filter sessions using text search query', async ({ page }) => {
    await setupMockBackend(page)

    await page.goto('/history')

    const searchInput = page.locator('[data-test="history-search-input"]')
    await expect(searchInput).toBeVisible()

    // Filter by specific keyword
    await searchInput.fill('FastAPI')

    const sessionCards = page.locator('[data-test="session-card"]')
    await expect(sessionCards).toHaveCount(1)
    await expect(sessionCards.first()).toContainText('FastAPI')
  })

  test('should restore session into chat and keep HITL controls closed', async ({
    page,
  }) => {
    await setupMockBackend(page)

    await page.goto('/history')

    // Select session "deb-002" which contains historic HITL events
    const hitlSessionCard = page.locator('[data-test="session-card"]').filter({
      hasText: 'Auditoría HITL de seguridad',
    })
    await expect(hitlSessionCard).toBeVisible()
    await hitlSessionCard.click()

    // Must return to main view
    await expect(page).toHaveURL('http://127.0.0.1:5173/')

    // Previous messages restored in chat
    await expect(page.locator('text=Auditoría HITL de seguridad')).toBeVisible()

    // CRITICAL REQUIREMENT: When returning from history, HITL must remain closed/inactive
    const hitlCard = page.locator('[data-test="hitl-chat-card"]')
    await expect(hitlCard).not.toBeVisible()
  })

  test('should delete session from history after confirming browser dialog', async ({
    page,
  }) => {
    await setupMockBackend(page)

    await page.goto('/history')

    const initialCards = page.locator('[data-test="session-card"]')
    await expect(initialCards.first()).toBeVisible()
    const initialCount = await initialCards.count()

    // Automatically accept browser window.confirm() dialog
    page.once('dialog', async (dialog) => {
      await dialog.accept()
    })

    const deleteBtn = page.locator('[data-test="delete-session-btn"]').first()
    await deleteBtn.click()

    // Session count decreases by 1
    await expect(page.locator('[data-test="session-card"]')).toHaveCount(initialCount - 1)
  })
})
