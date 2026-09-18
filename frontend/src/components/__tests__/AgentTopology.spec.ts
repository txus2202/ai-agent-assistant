import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import AgentTopology from '../AgentTopology.vue'

// Mocking Element.scrollIntoView since JSDOM doesn't implement it
Element.prototype.scrollIntoView = vi.fn()

describe('AgentTopology.vue', () => {
  it('renders a scrollable container for agents', () => {
    const wrapper = mount(AgentTopology, {
      props: {
        agents: []
      }
    })
    
    const container = wrapper.find('[data-test="topology-scroll-container"]')
    expect(container.exists()).toBe(true)
    expect(container.classes()).toContain('overflow-y-auto')
  })

  it('calls scrollIntoView when an agent becomes active', async () => {
    const wrapper = mount(AgentTopology, {
      props: {
        agents: [
          { role: 'nl_interpreter', name: 'NL INTERPRETER', state: 'STANDBY' },
          { role: 'senior_architect', name: 'SENIOR ARCHITECT', state: 'STANDBY' }
        ]
      }
    })

    // Cambiamos el prop simulando que un agente se vuelve activo
    await wrapper.setProps({
      agents: [
        { role: 'nl_interpreter', name: 'NL INTERPRETER', state: 'STANDBY' },
        { role: 'senior_architect', name: 'SENIOR ARCHITECT', state: 'ACTIVE' }
      ]
    })

    // Vue actualiza el DOM de forma asíncrona, esperamos al render completo
    await flushPromises()
    
    expect(Element.prototype.scrollIntoView).toHaveBeenCalledWith({
      behavior: 'smooth',
      block: 'center'
    })
  })
})
