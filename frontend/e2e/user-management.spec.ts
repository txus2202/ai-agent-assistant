import { test, expect } from '@playwright/test'
import { setupMockBackend } from './helpers/mockBackend'

test.describe('User Management (Administration)', () => {
  test('should allow an administrator to open modal and create a new user', async ({ page }) => {
    await setupMockBackend(page, {
      isAdmin: true,
      username: 'admin',
    })

    await page.goto('/')

    // Open user menu
    await page.click('[data-test="user-menu-btn"]')

    // Click "Gestión de Usuarios"
    const manageUsersBtn = page.locator('[data-test="manage-users-btn"]')
    await expect(manageUsersBtn).toBeVisible()
    await manageUsersBtn.click()

    // Management modal opens
    const modal = page.locator('[data-test="user-management-modal-backdrop"]')
    await expect(modal).toBeVisible()

    // Fill user creation form
    await page.fill('[data-test="username-input"]', 'nuevo_ingeniero')
    await page.fill('[data-test="password-input"]', 'PasswordSegura2026')
    await page.fill('[data-test="confirm-password-input"]', 'PasswordSegura2026')
    await page.check('[data-test="is-admin-checkbox"]')

    await page.click('[data-test="submit-user-btn"]')

    // Success banner shown and user listed in table
    await expect(page.locator('[data-test="success-banner"]')).toBeVisible()
    await expect(page.locator('[data-test="user-item"]').filter({ hasText: 'nuevo_ingeniero' })).toBeVisible()

    // Close modal
    await page.click('[data-test="close-modal-btn"]')
    await expect(modal).not.toBeVisible()
  })

  test('should not show user management option if user is not an administrator', async ({
    page,
  }) => {
    await setupMockBackend(page, {
      isAdmin: false,
      username: 'operador_estandar',
    })

    await page.goto('/')

    await page.click('[data-test="user-menu-btn"]')
    await expect(page.locator('[data-test="user-menu-dropdown"]')).toBeVisible()

    // User management action button must not be visible for standard users
    await expect(page.locator('[data-test="manage-users-btn"]')).not.toBeVisible()
  })
})
