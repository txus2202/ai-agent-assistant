import { ref } from 'vue'

const isDarkMode = ref(true)

export function useTheme() {
  const applyTheme = (dark: boolean) => {
    if (typeof document !== 'undefined') {
      const el = document.documentElement
      if (dark) {
        el.classList.add('dark')
        el.classList.remove('light')
      } else {
        el.classList.remove('dark')
        el.classList.add('light')
      }
    }
  }

  const initTheme = () => {
    if (typeof window === 'undefined') return
    const saved = localStorage.getItem('atenea_theme')
    // Default is always dark mode unless explicitly saved as 'light'
    if (saved === 'light') {
      isDarkMode.value = false
      applyTheme(false)
    } else {
      isDarkMode.value = true
      applyTheme(true)
    }
  }

  const toggleTheme = () => {
    isDarkMode.value = !isDarkMode.value
    applyTheme(isDarkMode.value)
    if (typeof window !== 'undefined') {
      localStorage.setItem('atenea_theme', isDarkMode.value ? 'dark' : 'light')
    }
  }

  return {
    isDarkMode,
    toggleTheme,
    initTheme,
    applyTheme
  }
}
