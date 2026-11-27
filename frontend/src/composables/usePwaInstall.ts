import { ref, computed, onMounted, onUnmounted } from 'vue'

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed'; platform?: string }>
}

interface NavigatorWithWebInstall extends Navigator {
  install?: () => Promise<void>
}

function isRunningStandalone(): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return false
  }
  return window.matchMedia('(display-mode: standalone)').matches
}

function hasNativeWebInstallSupport(): boolean {
  if (typeof Navigator === 'undefined') {
    return false
  }
  return typeof (Navigator.prototype as NavigatorWithWebInstall).install === 'function'
}

/**
 * Progressive-enhancement PWA installation composable.
 * Uses the modern Web Install API (`navigator.install()`) when supported and falls back
 * to `beforeinstallprompt` on Chromium browsers, staying hidden everywhere else.
 */
export function usePwaInstall() {
  const supportsWebInstall = ref(false)
  const deferredInstallPrompt = ref<BeforeInstallPromptEvent | null>(null)
  const isInstalled = ref(false)
  const isInstalling = ref(false)
  const installStatus = ref('')

  const canInstall = computed(() => {
    if (isInstalled.value) {
      return false
    }
    return supportsWebInstall.value || deferredInstallPrompt.value !== null
  })

  const handleBeforeInstallPrompt = (rawEvent: Event) => {
    rawEvent.preventDefault()
    deferredInstallPrompt.value = rawEvent as BeforeInstallPromptEvent
  }

  const handleAppInstalled = () => {
    deferredInstallPrompt.value = null
    isInstalled.value = true
    installStatus.value = 'Aplicación instalada correctamente.'
  }

  const installApp = async (): Promise<void> => {
    if (isInstalling.value || !canInstall.value) {
      return
    }

    isInstalling.value = true
    try {
      if (supportsWebInstall.value && typeof navigator !== 'undefined') {
        // Call directly inside the click handler to retain transient user activation
        await (navigator as NavigatorWithWebInstall).install!()
        isInstalled.value = true
        installStatus.value = 'Aplicación instalada o abierta correctamente.'
        return
      }

      if (deferredInstallPrompt.value) {
        // Save and clear single-use event before awaiting the user's choice
        const promptEvent = deferredInstallPrompt.value
        deferredInstallPrompt.value = null
        await promptEvent.prompt()
        const { outcome } = await promptEvent.userChoice
        if (outcome === 'accepted') {
          isInstalled.value = true
          installStatus.value = 'Aplicación instalada correctamente.'
        } else {
          installStatus.value = 'Instalación cancelada.'
        }
      }
    } catch (error) {
      const errName =
        error && typeof error === 'object' && 'name' in error
          ? String((error as { name?: unknown }).name)
          : ''
      if (errName === 'AbortError') {
        installStatus.value = 'Instalación cancelada.'
      } else {
        installStatus.value = 'No se pudo iniciar la instalación.'
        console.error('PWA install error:', error)
      }
    } finally {
      isInstalling.value = false
    }
  }

  onMounted(() => {
    isInstalled.value = isRunningStandalone()
    supportsWebInstall.value = hasNativeWebInstallSupport()
    if (typeof window !== 'undefined') {
      window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
      window.addEventListener('appinstalled', handleAppInstalled)
    }
  })

  onUnmounted(() => {
    if (typeof window !== 'undefined') {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
      window.removeEventListener('appinstalled', handleAppInstalled)
    }
  })

  return {
    canInstall,
    isInstalling,
    installStatus,
    installApp,
  }
}
