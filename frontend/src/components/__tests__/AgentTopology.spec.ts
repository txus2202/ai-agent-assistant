import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import AgentTopology from '../AgentTopology.vue'

vi.mock('../../stores/config', () => ({
  useConfigStore: () => ({
    agentsConfig: [],
    updateAgentConfig: vi.fn()
  })
}))

// Mocking Element.scrollIntoView since JSDOM doesn't implement it
Element.prototype.scrollIntoView = vi.fn()

describe('AgentTopology.vue', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

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

  it('renders supervisor agent as a card at the top of the list', () => {
    const wrapper = mount(AgentTopology, {
      props: {
        agents: [
          { role: 'nl_interpreter', name: 'NL Interpreter', state: 'STANDBY', color_hex: '#00e5ff' },
          { role: 'supervisor', name: 'Atenea (Supervisor)', state: 'STANDBY', color_hex: '#f59e0b' },
          { role: 'senior_architect', name: 'Senior Architect', state: 'STANDBY', color_hex: '#00ff9d' }
        ]
      }
    })

    const text = wrapper.text()
    expect(text).toContain('Atenea (Supervisor)')
    expect(text).toContain('NL Interpreter')
    expect(text).toContain('Senior Architect')
  })

  it('switches between Agentes and Observabilidad tabs', async () => {
    const wrapper = mount(AgentTopology, {
      props: {
        agents: [
          { role: 'nl_interpreter', name: 'NL Interpreter', state: 'STANDBY', color_hex: '#00e5ff' }
        ]
      }
    })

    // Initially on agents tab
    const agentsTab = wrapper.find('[data-test="tab-agents"]')
    const obsTab = wrapper.find('[data-test="tab-observability"]')
    expect(agentsTab.exists()).toBe(true)
    expect(obsTab.exists()).toBe(true)
    expect(agentsTab.classes()).toContain('text-neon-cyan')
    expect(wrapper.find('[data-test="topology-scroll-container"]').exists()).toBe(true)

    // Switch to Observability tab
    await obsTab.trigger('click')
    expect(obsTab.classes()).toContain('text-neon-cyan')
    expect(wrapper.text()).toContain('SYSTEM OBSERVABILITY')
    expect(wrapper.find('[data-test="topology-scroll-container"]').exists()).toBe(false)

    // Switch back to Agentes tab
    await agentsTab.trigger('click')
    expect(agentsTab.classes()).toContain('text-neon-cyan')
    expect(wrapper.find('[data-test="topology-scroll-container"]').exists()).toBe(true)
  })
})


