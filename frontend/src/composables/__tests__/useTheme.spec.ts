import { describe, it, expect, beforeEach } from 'vitest'
import { useTheme } from '../useTheme'

describe('useTheme composable', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.className = ''
  })

  it('defaults to dark mode if no saved theme', () => {
    const { isDarkMode, initTheme } = useTheme()
    initTheme()
    expect(isDarkMode.value).toBe(true)
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(document.documentElement.classList.contains('light')).toBe(false)
  })

  it('loads light mode if saved in localStorage', () => {
    localStorage.setItem('atenea_theme', 'light')
    const { isDarkMode, initTheme } = useTheme()
    initTheme()
    expect(isDarkMode.value).toBe(false)
    expect(document.documentElement.classList.contains('light')).toBe(true)
    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })

  it('toggles between dark and light mode and persists to localStorage', () => {
    const { isDarkMode, initTheme, toggleTheme } = useTheme()
    initTheme()
    expect(isDarkMode.value).toBe(true)

    // Toggle to light
    toggleTheme()
    expect(isDarkMode.value).toBe(false)
    expect(document.documentElement.classList.contains('light')).toBe(true)
    expect(localStorage.getItem('atenea_theme')).toBe('light')

    // Toggle back to dark
    toggleTheme()
    expect(isDarkMode.value).toBe(true)
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(localStorage.getItem('atenea_theme')).toBe('dark')
  })
})

