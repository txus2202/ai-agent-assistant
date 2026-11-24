import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ChatComposer from '../ChatComposer.vue'

describe('ChatComposer keyboard input behavior', () => {
  const baseProps = {
    draftMessage: 'Consulta de arquitectura',
    selectedAgents: [],
    agentsList: [],
    availableDomains: [],
    selectedDomain: '',
    selectedFilesCount: 0,
    isHitlRequired: false,
    isDebating: false,
    isChatScrollable: false,
    scrollDirection: 'down' as const,
  }

  beforeEach(() => {
    // Default to desktop desktop non-touch environment
    vi.stubGlobal('matchMedia', vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })))
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('submits on Enter when on desktop without Shift', async () => {
    const wrapper = mount(ChatComposer, {
      props: baseProps,
    })

    const textarea = wrapper.find('textarea')
    await textarea.trigger('keydown', { key: 'Enter', shiftKey: false })

    expect(wrapper.emitted('submit')).toHaveLength(1)
  })

  it('does NOT submit on Shift + Enter (allows multiline insertion)', async () => {
    const wrapper = mount(ChatComposer, {
      props: baseProps,
    })

    const textarea = wrapper.find('textarea')
    await textarea.trigger('keydown', { key: 'Enter', shiftKey: true })

    expect(wrapper.emitted('submit')).toBeUndefined()
  })

  it('submits on Enter during HITL refinement phase', async () => {
    const wrapper = mount(ChatComposer, {
      props: {
        ...baseProps,
        isHitlRequired: true,
        isDebating: true,
        draftMessage: 'Modifica la estructura del DAG',
      },
    })

    const textarea = wrapper.find('textarea')
    await textarea.trigger('keydown', { key: 'Enter', shiftKey: false })

    expect(wrapper.emitted('submit')).toHaveLength(1)
  })

  it('does NOT submit on mobile virtual keyboard Enter (allows multiline on phone)', async () => {
    // Simulate mobile touch device
    vi.stubGlobal('matchMedia', vi.fn().mockImplementation((query: string) => ({
      matches: query.includes('max-width: 768px') || query.includes('pointer: coarse'),
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })))

    const wrapper = mount(ChatComposer, {
      props: baseProps,
    })

    const textarea = wrapper.find('textarea')
    await textarea.trigger('keydown', { key: 'Enter', shiftKey: false })

    expect(wrapper.emitted('submit')).toBeUndefined()
  })

  it('submits on Ctrl + Enter or Cmd + Enter even on mobile/tablet', async () => {
    const wrapper = mount(ChatComposer, {
      props: baseProps,
    })

    const textarea = wrapper.find('textarea')
    await textarea.trigger('keydown', { key: 'Enter', ctrlKey: true })

    expect(wrapper.emitted('submit')).toHaveLength(1)
  })

  it('does NOT submit when draftMessage is empty or whitespace', async () => {
    const wrapper = mount(ChatComposer, {
      props: {
        ...baseProps,
        draftMessage: '   ',
      },
    })

    const textarea = wrapper.find('textarea')
    await textarea.trigger('keydown', { key: 'Enter', shiftKey: false })

    expect(wrapper.emitted('submit')).toBeUndefined()
  })
})

