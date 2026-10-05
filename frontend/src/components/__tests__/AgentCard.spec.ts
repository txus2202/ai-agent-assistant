import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import AgentCard from '../AgentCard.vue'

const mockUpdateAgentConfig = vi.fn()

vi.mock('../../stores/config', () => ({
  useConfigStore: () => ({
    agentsConfig: [{ id: 'THE_JUDGE', provider: 'gemini', model_name: 'gemini-1.5-flash' }, { id: 'the_judge', provider: 'gemini', model_name: 'gemini-1.5-flash' }],
    providers: [
      { id: 'gemini', name: 'Gemini', models: [{ id: 'gemini-1.5-flash', name: 'Gemini Flash' }] },
      { id: 'openai', name: 'OpenAI', models: [{ id: 'gpt-4o-mini', name: 'GPT 4o Mini' }] }
    ],
    updateAgentConfig: mockUpdateAgentConfig
  })
}))

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

  it('renders provider and model selects and updates config store', async () => {
    const { useConfigStore } = await import('../../stores/config')
    const store = useConfigStore()

    const wrapper = mount(AgentCard, {
      props: {
        role: 'the_judge',
        state: 'STANDBY',
        colorClass: 'text-rose-400',
        glowClass: 'glow-red'
      }
    })

    const providerSelect = wrapper.find('[data-test="provider-select"]')
    const modelSelect = wrapper.find('[data-test="model-select"]')
    
    expect(providerSelect.exists()).toBe(true)
    expect(modelSelect.exists()).toBe(true)
    
    expect((providerSelect.element as HTMLSelectElement).value).toBe('gemini')
    expect((modelSelect.element as HTMLSelectElement).value).toBe('gemini-1.5-flash')

    await providerSelect.setValue('openai')
    expect(mockUpdateAgentConfig).toHaveBeenCalledWith('the_judge', 'openai', 'gpt-4o-mini')
  })
})
