import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import AgentCard from '../AgentCard.vue'

const mockUpdateAgentConfig = vi.fn()

vi.mock('../../stores/config', () => ({
  useConfigStore: () => ({
    agentsConfig: [
      { id: 'THE_JUDGE', provider: 'gemini', model_name: 'gemini-1.5-flash', description: "Evaluates trade-offs and acts as Devil's Advocate" },
      { id: 'the_judge', provider: 'gemini', model_name: 'gemini-1.5-flash', description: "Evaluates trade-offs and acts as Devil's Advocate" }
    ],
    providers: [
      { id: 'gemini', name: 'Gemini', models: [{ id: 'gemini-1.5-flash', name: 'Gemini Flash' }, { id: 'gemini-1.5-pro', name: 'Gemini Pro' }] },
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

    await modelSelect.setValue('gemini-1.5-pro')
    expect(mockUpdateAgentConfig).toHaveBeenCalledWith('the_judge', 'gemini', 'gemini-1.5-pro')
  })

  it('renders tokens consumed and latency badges when provided', () => {
    const wrapper = mount(AgentCard, {
      props: {
        role: 'the_judge',
        state: 'ACTIVE',
        colorClass: 'text-rose-400',
        glowClass: 'glow-red',
        tokensConsumed: 1250,
        latencySeconds: 0.85
      }
    })

    expect(wrapper.text()).toContain('1250')
    expect(wrapper.text()).toContain('0.85s')
  })

  it('renders breakdown of input and output tokens', () => {
    const wrapper = mount(AgentCard, {
      props: {
        role: 'the_judge',
        state: 'ACTIVE',
        promptTokens: 320,
        completionTokens: 850
      }
    })

    expect(wrapper.text()).toContain('In:320')
    expect(wrapper.text()).toContain('Out:850')
  })

  it('renders always-visible agent mission description', () => {
    const wrapper = mount(AgentCard, {
      props: {
        role: 'the_judge',
        state: 'STANDBY',
        colorClass: 'text-rose-400',
        glowClass: 'glow-red'
      }
    })

    const desc = wrapper.find('[data-test="agent-description"]')
    expect(desc.exists()).toBe(true)
    expect(desc.text()).toContain("Devil's Advocate")
  })

  it('renders description from props when provided', () => {
    const wrapper = mount(AgentCard, {
      props: {
        role: 'the_judge',
        description: 'Descripción recibida desde el backend',
        state: 'STANDBY',
        colorClass: 'text-rose-400',
        glowClass: 'glow-red'
      }
    })

    const desc = wrapper.find('[data-test="agent-description"]')
    expect(desc.text()).toBe('Descripción recibida desde el backend')
  })

  it('applies dynamic colorHex to title and active card border', () => {
    const wrapper = mount(AgentCard, {
      props: {
        role: 'INNOVATOR',
        state: 'ACTIVE',
        colorHex: '#22c55e'
      }
    })

    const title = wrapper.find('h3')
    expect(title.attributes('style')).toContain('color: rgb(34, 197, 94)')
    const cardEl = wrapper.find('[data-test="card-container"]')
    expect(cardEl.attributes('style')).toContain('border-color: rgb(34, 197, 94)')
  })

  it('renders ERROR status tag and does not display progress bar when in ERROR state', () => {
    const wrapper = mount(AgentCard, {
      props: {
        role: 'THE_JUDGE',
        state: 'ERROR',
        colorHex: '#ef4444'
      }
    })

    expect(wrapper.text()).toContain('ERROR')
    const progressBar = wrapper.find('[data-test="progress-bar"]')
    expect(progressBar.exists()).toBe(false)
  })

  it('hides RAG configuration sliders when usesRag is false', () => {
    const wrapper = mount(AgentCard, {
      props: {
        role: 'THE_JUDGE',
        state: 'STANDBY',
        usesRag: false,
      }
    })

    expect(wrapper.find('[data-test="rag-config-controls"]').exists()).toBe(false)
  })

  it('renders RAG configuration sliders when usesRag is true and updates config store', async () => {
    mockUpdateAgentConfig.mockClear()
    const wrapper = mount(AgentCard, {
      props: {
        role: 'the_judge',
        state: 'STANDBY',
        usesRag: true,
      }
    })

    const ragControls = wrapper.find('[data-test="rag-config-controls"]')
    expect(ragControls.exists()).toBe(true)

    const topKSlider = wrapper.find('[data-test="rag-top-k-slider"]')
    const minScoreSlider = wrapper.find('[data-test="rag-min-score-slider"]')
    expect(topKSlider.exists()).toBe(true)
    expect(minScoreSlider.exists()).toBe(true)

    expect(wrapper.find('[data-test="rag-top-k-value"]').text()).toBe('5')
    expect(wrapper.find('[data-test="rag-min-score-value"]').text()).toBe('0.30')

    await topKSlider.setValue('12')
    expect(mockUpdateAgentConfig).toHaveBeenCalledWith('the_judge', 'gemini', 'gemini-1.5-flash', 12, 0.3)
    expect(wrapper.find('[data-test="rag-top-k-value"]').text()).toBe('12')

    await minScoreSlider.setValue('0.55')
    expect(mockUpdateAgentConfig).toHaveBeenCalledWith('the_judge', 'gemini', 'gemini-1.5-flash', 12, 0.55)
    expect(wrapper.find('[data-test="rag-min-score-value"]').text()).toBe('0.55')

    await topKSlider.setValue('0')
    expect(wrapper.find('[data-test="rag-top-k-value"]').text()).toBe('OFF')
    expect((minScoreSlider.element as HTMLInputElement).disabled).toBe(true)
  })
})

