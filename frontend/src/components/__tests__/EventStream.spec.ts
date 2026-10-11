import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import EventStream from '../EventStream.vue'

describe('EventStream.vue', () => {
  it('renders awaiting telemetry message when events list is empty', () => {
    const wrapper = mount(EventStream, {
      props: { events: [] }
    })

    expect(wrapper.text()).toContain('Awaiting telemetry...')
    expect(wrapper.text()).toContain('0 events')
  })

  it('renders events with formatted timestamp and details', () => {
    const events = [
      {
        timestamp: '2026-10-11T12:30:45.123Z',
        type: 'agent_started',
        role: 'nl_interpreter',
        detail: 'Parsing user prompt'
      },
      {
        timestamp: '2026-10-11T12:30:46.456Z',
        type: 'agent_completed',
        role: 'nl_interpreter',
        result: 'Done'
      },
      {
        timestamp: '2026-10-11T12:30:47.789Z',
        type: 'hitl_required',
        checkpoint: 'CP-1'
      },
      {
        timestamp: '2026-10-11T12:30:48.012Z',
        type: 'error',
        message: 'Timeout error'
      },
      {
        timestamp: '2026-10-11T12:30:49.000Z',
        type: 'custom_ping',
        payload: 42
      }
    ]

    const wrapper = mount(EventStream, {
      props: { events }
    })

    expect(wrapper.text()).toContain('5 events')
    expect(wrapper.text()).toContain('AGENT_STARTED')
    expect(wrapper.text()).toContain('AGENT_COMPLETED')
    expect(wrapper.text()).toContain('HITL_REQUIRED')
    expect(wrapper.text()).toContain('ERROR')
    expect(wrapper.text()).toContain('CUSTOM_PING')
    expect(wrapper.text()).toContain('[nl_interpreter]')
    expect(wrapper.text()).toContain('"detail":"Parsing user prompt"')

    // Color classes within the list container
    const list = wrapper.find({ ref: 'listContainer' })
    const agentStarted = list.find('.text-neon-cyan')
    expect(agentStarted.exists()).toBe(true)
    expect(agentStarted.text()).toBe('AGENT_STARTED')

    const agentCompleted = list.find('.text-neon-green')
    expect(agentCompleted.exists()).toBe(true)
    expect(agentCompleted.text()).toBe('AGENT_COMPLETED')

    const hitlRequired = list.find('.text-neon-amber')
    expect(hitlRequired.exists()).toBe(true)
    expect(hitlRequired.text()).toBe('HITL_REQUIRED')

    const errorEvent = list.find('.text-neon-red')
    expect(errorEvent.exists()).toBe(true)
    expect(errorEvent.text()).toBe('ERROR')

    const customEvent = list.find('.text-space-300')
    expect(customEvent.exists()).toBe(true)
    expect(customEvent.text()).toBe('CUSTOM_PING')
  })

  it('scrolls container to bottom when new events are added', async () => {
    const events = [{ timestamp: '2026-10-11T12:00:00.000Z', type: 'init' }]
    const wrapper = mount(EventStream, {
      props: { events }
    })

    const scrollContainer = wrapper.find({ ref: 'listContainer' }).element as HTMLElement
    Object.defineProperty(scrollContainer, 'scrollHeight', { value: 500, configurable: true })

    await wrapper.setProps({
      events: [...events, { timestamp: '2026-10-11T12:00:01.000Z', type: 'agent_started' }]
    })
    await nextTick()

    expect(scrollContainer.scrollTop).toBe(500)
  })
})
