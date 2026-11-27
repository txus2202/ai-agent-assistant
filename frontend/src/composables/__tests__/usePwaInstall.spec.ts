import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { usePwaInstall } from '../usePwaInstall'

function createHarness() {
  return defineComponent({
    setup() {
      return usePwaInstall()
    },
    template: '<div></div>',
  })
}

describe('usePwaInstall composable', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    // Ensure Navigator.prototype.install is absent by default
    delete (Navigator.prototype as { install?: unknown }).install
  })

  it('stays hidden (canInstall = false) when neither navigator.install nor beforeinstallprompt is available', () => {
    const wrapper = mount(createHarness())
    expect(wrapper.vm.canInstall).toBe(false)
    expect(wrapper.vm.isInstalling).toBe(false)
    wrapper.unmount()
  })

  it('captures beforeinstallprompt, clears single-use event before awaiting prompt, and hides after acceptance', async () => {
    const wrapper = mount(createHarness())

    const promptSpy = vi.fn().mockResolvedValue(undefined)
    const promptEvent = new Event('beforeinstallprompt', { cancelable: true }) as Event & {
      prompt: () => Promise<void>
      userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
    }
    promptEvent.prompt = promptSpy
    promptEvent.userChoice = Promise.resolve({ outcome: 'accepted' })

    window.dispatchEvent(promptEvent)
    expect(promptEvent.defaultPrevented).toBe(true)
    expect(wrapper.vm.canInstall).toBe(true)

    await wrapper.vm.installApp()

    expect(promptSpy).toHaveBeenCalledOnce()
    expect(wrapper.vm.canInstall).toBe(false)
    expect(wrapper.vm.installStatus).toContain('instalada')
    wrapper.unmount()
  })

  it('uses navigator.install() when supported and keeps button available on AbortError cancellation', async () => {
    const abortErr = new DOMException('User canceled', 'AbortError')
    const installSpy = vi.fn().mockRejectedValueOnce(abortErr).mockResolvedValueOnce(undefined)
    Object.defineProperty(Navigator.prototype, 'install', {
      value: installSpy,
      configurable: true,
      writable: true,
    })

    const wrapper = mount(createHarness())
    expect(wrapper.vm.canInstall).toBe(true)

    // First attempt: user cancels -> AbortError -> remains available to retry
    await wrapper.vm.installApp()
    expect(installSpy).toHaveBeenCalledTimes(1)
    expect(wrapper.vm.canInstall).toBe(true)
    expect(wrapper.vm.isInstalling).toBe(false)
    expect(wrapper.vm.installStatus).toBe('Instalación cancelada.')

    // Second attempt: succeeds -> hides install button
    await wrapper.vm.installApp()
    expect(installSpy).toHaveBeenCalledTimes(2)
    expect(wrapper.vm.canInstall).toBe(false)
    wrapper.unmount()
  })

  it('handles dismissed beforeinstallprompt outcome and appinstalled browser event', async () => {
    const wrapper = mount(createHarness())

    const dismissedEvent = new Event('beforeinstallprompt', { cancelable: true }) as Event & {
      prompt: () => Promise<void>
      userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
    }
    dismissedEvent.prompt = vi.fn().mockResolvedValue(undefined)
    dismissedEvent.userChoice = Promise.resolve({ outcome: 'dismissed' })

    window.dispatchEvent(dismissedEvent)
    await wrapper.vm.installApp()
    expect(wrapper.vm.installStatus).toBe('Instalación cancelada.')
    expect(wrapper.vm.canInstall).toBe(false)

    // Re-offer and complete via native appinstalled event
    window.dispatchEvent(dismissedEvent)
    expect(wrapper.vm.canInstall).toBe(true)
    window.dispatchEvent(new Event('appinstalled'))
    expect(wrapper.vm.canInstall).toBe(false)
    expect(wrapper.vm.installStatus).toContain('instalada')
    wrapper.unmount()
  })
})
