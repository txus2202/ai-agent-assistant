import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import HITLActionButton from '../HITLActionButton.vue'

describe('HITLActionButton.vue', () => {
  it('displays APPROVE text and emits approve event when decision is approve', async () => {
    const wrapper = mount(HITLActionButton, {
      props: {
        decision: 'approve',
        disabled: false
      }
    })
    
    expect(wrapper.text()).toContain('APPROVE')
    
    await wrapper.trigger('click')
    expect(wrapper.emitted('action')).toBeTruthy()
    expect(wrapper.emitted('action')![0]).toEqual(['approve'])
  })

  it('is disabled when disabled prop is true', async () => {
    const wrapper = mount(HITLActionButton, {
      props: {
        decision: 'refine',
        disabled: true
      }
    })
    
    const button = wrapper.find('button')
    expect(button.element.disabled).toBe(true)
    
    await wrapper.trigger('click')
    expect(wrapper.emitted('action')).toBeFalsy()
  })
})
