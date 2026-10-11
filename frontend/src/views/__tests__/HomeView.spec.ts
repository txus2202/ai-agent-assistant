import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import HomeView from '../HomeView.vue'

describe('HomeView.vue', () => {
  it('renders main layout and AppShell component', () => {
    const wrapper = mount(HomeView, {
      global: {
        stubs: {
          AppShell: { template: '<div data-test="app-shell-stub">AppShell Content</div>' }
        }
      }
    })

    const main = wrapper.find('main')
    expect(main.exists()).toBe(true)
    expect(main.classes()).toContain('h-full')
    expect(main.classes()).toContain('w-full')
    expect(wrapper.find('[data-test="app-shell-stub"]').exists()).toBe(true)
  })
})
