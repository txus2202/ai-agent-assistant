import { test, expect } from '@playwright/test'
import { setupMockBackend } from './helpers/mockBackend'

test.describe('Authentication and Initial Setup', () => {
  test('should redirect to setup if backend is uninitialized and allow completing configuration', async ({
    page,
  }) => {
    await setupMockBackend(page, {
      initialized: false,
      setupTokenRequired: true,
      authenticated: false,
    })

    await page.goto('/')

    // Should automatically redirect to /setup
    await expect(page).toHaveURL(/.*\/setup/)
    await expect(page.locator('h1')).toContainText('A.T.E.N.E.A.')
    await expect(page.getByText('Creación de Cuenta Administrador')).toBeVisible()

    // Fill setup form
    await page.fill('#setup-username', 'superadmin')
    await page.fill('#setup-password', 'AdminSecret1234')
    await page.fill('#setup-confirm-password', 'AdminSecret1234')
    await page.fill('#setup-token', 'atenea-initial-token')

    await page.click('button[type="submit"]')

    // On success, redirect to dashboard
    await expect(page).toHaveURL('http://127.0.0.1:5173/')
  })

  test('should redirect to login if unauthenticated and display error on invalid credentials', async ({
    page,
  }) => {
    await setupMockBackend(page, {
      initialized: true,
      authenticated: false,
    })

    await page.goto('/')
    await expect(page).toHaveURL(/.*\/login/)

    // Attempt login with invalid credentials
    await page.fill('#login-username', 'invalid_user')
    await page.fill('#login-password', 'wrong_password')
    await page.click('button[type="submit"]')

    // Verify error message
    const errorAlert = page.locator('div').filter({ hasText: 'Credenciales inválidas' })
    await expect(errorAlert.first()).toBeVisible()
  })

  test('should login successfully with valid credentials and redirect to dashboard', async ({
    page,
  }) => {
    await setupMockBackend(page, {
      initialized: true,
      authenticated: false,
    })

    await page.goto('/login')

    await page.fill('#login-username', 'admin')
    await page.fill('#login-password', 'admin1234')
    await page.click('button[type="submit"]')

    // Redirect to main dashboard
    await expect(page).toHaveURL('http://127.0.0.1:5173/')
    await expect(page.locator('[data-test="header-left-section"]')).toBeVisible()
  })

  test('should allow logging out from user menu in header', async ({ page }) => {
    await setupMockBackend(page, {
      initialized: true,
      authenticated: true,
      username: 'operador_atenea',
    })

    await page.goto('/')
    await expect(page.locator('[data-test="user-menu-btn"]')).toBeVisible()

    // Open user menu
    await page.click('[data-test="user-menu-btn"]')
    await expect(page.locator('[data-test="user-menu-dropdown"]')).toBeVisible()

    // Click logout
    await page.click('[data-test="logout-btn"]')

    // Should redirect to /login
    await expect(page).toHaveURL(/.*\/login/)
  })

  test('route guards should prevent accessing login when already authenticated', async ({
    page,
  }) => {
    await setupMockBackend(page, {
      initialized: true,
      authenticated: true,
    })

    await page.goto('/login')
    // guestOnly guard automatically redirects back to /
    await expect(page).toHaveURL('http://127.0.0.1:5173/')
  })
})
