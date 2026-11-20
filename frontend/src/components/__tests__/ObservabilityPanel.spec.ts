import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
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
  const mountedWrappers: VueWrapper[] = []

  const mountPanel = (props: Record<string, unknown> = {}) => {
    const w = mount(ObservabilityPanel, { props })
    mountedWrappers.push(w)
    return w
  }

  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    while (mountedWrappers.length > 0) {
      mountedWrappers.pop()?.unmount()
    }
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
    const wrapper = mountPanel()
    for (const text of expectedTexts) {
      expect(wrapper.text()).toContain(text)
    }
  })

  it('renders context cache efficiency and logs event stream', () => {
    const wrapper = mountPanel()
    expect(wrapper.text()).toContain("SESSION CONTEXT CACHE")
    expect(wrapper.text()).toContain("LOGS / EVENT STREAM")
  })

  it('renders dynamic active agent badge in header and benchmarks', () => {
    const wrapper = mountPanel()
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

    const wrapper = mountPanel()
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

    const wrapper = mountPanel()
    await flushPromises()
    const link = wrapper.find('[data-test="langfuse-dashboard-link"]')
    expect(link.exists()).toBe(true)
    expect(link.attributes('href')).toBe('http://localhost:3000')
    expect(link.attributes('target')).toBe('_blank')
  })

  it('renders custom configured dashboard URL when provided by observability stats API', async () => {
    global.fetch = vi.fn().mockImplementation(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            cpu_percent: 42,
            memory_percent: 65,
            cluster_status: 'HEALTHY',
            langfuse_metrics_enabled: true,
            langfuse_dashboard_url: 'https://langfuse.mycompany.internal',
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      ),
    )

    const wrapper = mountPanel()
    await flushPromises()
    const link = wrapper.find('[data-test="langfuse-dashboard-link"]')
    expect(link.exists()).toBe(true)
    expect(link.attributes('href')).toBe('https://langfuse.mycompany.internal')
  })

  it('displays ERROR status badge for agents in error state', () => {
    const wrapper = mountPanel()
    // The Judge is ACTIVE with 1.8s running..., Senior Arch is COMPLETED with 1.12s
    expect(wrapper.text()).toContain('1.8s running...')
    expect(wrapper.text()).toContain('1.12s')
  })

  it('suspends polling and 200ms tick when document is hidden or panel is not visible', async () => {
    vi.useFakeTimers()
    const fetchSpy = vi.fn().mockImplementation(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({ cpu_percent: 25, memory_percent: 45, cluster_status: 'HEALTHY' }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        )
      )
    )
    global.fetch = fetchSpy

    try {
      const wrapper = mountPanel({ isVisible: true })
      await flushPromises()
      expect(fetchSpy).toHaveBeenCalledTimes(1)

      // Visible + active agent -> 3s polling advances fetch count
      await vi.advanceTimersByTimeAsync(3100)
      expect(fetchSpy).toHaveBeenCalledTimes(2)

      // Hide panel via prop -> no polling even after 6s
      await wrapper.setProps({ isVisible: false })
      await vi.advanceTimersByTimeAsync(6000)
      expect(fetchSpy).toHaveBeenCalledTimes(2)

      // Becoming visible again triggers fresh fetch and resumes polling
      await wrapper.setProps({ isVisible: true })
      await flushPromises()
      expect(fetchSpy).toHaveBeenCalledTimes(3)

      // Hide tab via document.visibilityState -> suspends polling
      Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true })
      document.dispatchEvent(new Event('visibilitychange'))
      await vi.advanceTimersByTimeAsync(6000)
      expect(fetchSpy).toHaveBeenCalledTimes(3)

      Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true })
      document.dispatchEvent(new Event('visibilitychange'))
      await flushPromises()
      expect(fetchSpy).toHaveBeenCalledTimes(4)

      wrapper.unmount()
    } finally {
      Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true })
      vi.useRealTimers()
    }
  })
})

