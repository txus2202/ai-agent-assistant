import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AgentCard from '../AgentCard.vue'

describe('AgentCard.vue', () => {
  it('renders agent role and dot color based on state', () => {
    const wrapper = mount(AgentCard, {
      props: {
        role: 'THE_JUDGE',
        state: 'STANDBY',
        colorClass: 'text-rose-400',
        glowClass: 'glow-red'
      }
    })
    
    // Debería mostrar el role (con espacios en vez de guiones bajos)
    expect(wrapper.text()).toContain('THE JUDGE')
    // Debería mostrar el estado
    expect(wrapper.text()).toContain('STANDBY')
    // Al estar en STANDBY, NO debería tener la clase glow
    expect(wrapper.classes()).not.toContain('glow-red')
  })

  it('applies glow class when state is ACTIVE', () => {
    const wrapper = mount(AgentCard, {
      props: {
        role: 'NL_INTERPRETER',
        state: 'ACTIVE',
        colorClass: 'text-cyan-300',
        glowClass: 'glow-cyan'
      }
    })
    
    // Al estar en ACTIVE, debería tener la clase glow para el borde
    const cardEl = wrapper.find('[data-test="card-container"]')
    expect(cardEl.classes()).toContain('glow-cyan')
    expect(wrapper.text()).toContain('ACTIVE CO-EXEC')
  })

  it('renders progress bar when ACTIVE', () => {
    const wrapper = mount(AgentCard, {
      props: {
        role: 'INNOVATOR',
        state: 'ACTIVE',
        colorClass: 'text-lime-400',
        glowClass: 'glow-green'
      }
    })

    const progressBar = wrapper.find('[data-test="progress-bar"]')
    expect(progressBar.exists()).toBe(true)
  })
  
  it('hides progress bar when STANDBY or COMPLETED', () => {
    const wrapper = mount(AgentCard, {
      props: {
        role: 'INNOVATOR',
        state: 'COMPLETED',
        colorClass: 'text-lime-400',
        glowClass: 'glow-green'
      }
    })

    const progressBar = wrapper.find('[data-test="progress-bar"]')
    expect(progressBar.exists()).toBe(false)
  })
})
