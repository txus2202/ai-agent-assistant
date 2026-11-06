import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ObservabilityPanel from '../ObservabilityPanel.vue'

vi.mock('../../stores/debate', () => ({
  useDebateStore: () => ({
    agents: [
      { id: 'nl_interpreter', role: 'NL_INTERPRETER', roleName: 'Interpreter', state: 'STANDBY', latency: 0.48 },
      { id: 'senior_architect', role: 'SENIOR_ARCHITECT', roleName: 'Senior Arch', state: 'COMPLETED', latency: 1.12 },
      { id: 'innovator_architect', role: 'INNOVATOR', roleName: 'Innovator Arch', state: 'COMPLETED', latency: 1.45 },
      { id: 'the_judge', role: 'THE_JUDGE', roleName: 'The Judge', state: 'ACTIVE', latency: 1.8 }
    ],
    rawEvents: [
      { type: 'SYSTEM', text: 'Architecture proposals merged' },
      { type: 'PIPELINE', text: 'Consensus packet handed over to The Judge' }
    ]
  })
}))

describe('ObservabilityPanel.vue', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it.each([
    {
      description: 'system observability title and healthy status',
      expectedTexts: ['SYSTEM OBSERVABILITY', 'HEALTHY']
    },
    {
      description: 'circular cluster audit gauge and hardware metrics',
      expectedTexts: ['CLUSTER', 'AUDIT ONLINE', 'CPU LOAD', 'MEMORY USAGE']
    },
    {
      description: 'agent latency benchmarks and progress bars',
      expectedTexts: ['AGENT LATENCY BENCHMARKS', 'Interpreter', '0.48s', 'The Judge']
    }
  ])('renders $description', ({ expectedTexts }) => {
    const wrapper = mount(ObservabilityPanel)
    for (const text of expectedTexts) {
      expect(wrapper.text()).toContain(text)
    }
  })

  it('renders context cache efficiency and logs event stream', () => {
    const wrapper = mount(ObservabilityPanel)
    expect(wrapper.text()).toContain("SESSION CONTEXT CACHE")
    expect(wrapper.text()).toContain("LOGS / EVENT STREAM")
  })

  it('renders dynamic active agent badge in header and benchmarks', () => {
    const wrapper = mount(ObservabilityPanel)
    expect(wrapper.text()).toContain("ACTIVE: 1 (THE JUDGE)")
  })

  it('hides external link to Langfuse dashboard when langfuse_metrics_enabled is false', async () => {
    global.fetch = vi.fn().mockImplementation(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            cpu_percent: 30,
            memory_percent: 50,
            cluster_status: 'HEALTHY',
            langfuse_metrics_enabled: false,
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      ),
    )

    const wrapper = mount(ObservabilityPanel)
    await flushPromises()
    const link = wrapper.find('[data-test="langfuse-dashboard-link"]')
    expect(link.exists()).toBe(false)
  })

  it('renders external link to Langfuse dashboard when langfuse_metrics_enabled is true', async () => {
    global.fetch = vi.fn().mockImplementation(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            cpu_percent: 42,
            memory_percent: 65,
            cluster_status: 'HEALTHY',
            langfuse_metrics_enabled: true,
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      ),
    )

    const wrapper = mount(ObservabilityPanel)
    await flushPromises()
    const link = wrapper.find('[data-test="langfuse-dashboard-link"]')
    expect(link.exists()).toBe(true)
    expect(link.attributes('href')).toBe('http://localhost:3000')
    expect(link.attributes('target')).toBe('_blank')
  })

  it('displays ERROR status badge for agents in error state', () => {
    const wrapper = mount(ObservabilityPanel)
    // The Judge is ACTIVE with 1.8s running..., Senior Arch is COMPLETED with 1.12s
    expect(wrapper.text()).toContain('1.8s running...')
    expect(wrapper.text()).toContain('1.12s')
  })
})

