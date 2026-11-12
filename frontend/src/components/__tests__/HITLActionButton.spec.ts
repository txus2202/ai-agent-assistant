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

  it('displays REJECT text and emits reject event when decision is reject', async () => {
    const wrapper = mount(HITLActionButton, {
      props: {
        decision: 'reject',
        disabled: false
      }
    })
    
    expect(wrapper.text()).toContain('REJECT / ABORT')
    expect(wrapper.classes()).toContain('border-neon-red')
    expect(wrapper.classes()).toContain('text-neon-red')
    
    await wrapper.trigger('click')
    expect(wrapper.emitted('action')).toBeTruthy()
    expect(wrapper.emitted('action')![0]).toEqual(['reject'])
  })

  it('displays REFINE text and has amber styling when decision is refine', async () => {
    const wrapper = mount(HITLActionButton, {
      props: {
        decision: 'refine',
        disabled: false
      }
    })
    
    expect(wrapper.text()).toContain('REFINE / ITERATE')
    expect(wrapper.classes()).toContain('border-neon-amber')
    expect(wrapper.classes()).toContain('text-neon-amber')

    await wrapper.trigger('click')
    expect(wrapper.emitted('action')).toBeTruthy()
    expect(wrapper.emitted('action')![0]).toEqual(['refine'])
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

  it('displays DIVERT text and emits divert event when decision is divert', async () => {
    const wrapper = mount(HITLActionButton, {
      props: {
        decision: 'divert',
        disabled: false
      }
    })

    expect(wrapper.text()).toContain('DIVERT / FORK')
    await wrapper.trigger('click')
    expect(wrapper.emitted('action')![0]).toEqual(['divert'])
  })

  it('displays FINISH text and emits finish event when decision is finish', async () => {
    const wrapper = mount(HITLActionButton, {
      props: {
        decision: 'finish',
        disabled: false
      }
    })

    expect(wrapper.text()).toContain('FINISH / HALT')
    await wrapper.trigger('click')
    expect(wrapper.emitted('action')![0]).toEqual(['finish'])
  })

  it('displays CONSOLIDATE text and emits consolidate event when decision is consolidate', async () => {
    const wrapper = mount(HITLActionButton, {
      props: {
        decision: 'consolidate',
        disabled: false
      }
    })

    expect(wrapper.text()).toContain('CONSOLIDATE / MERGE')
    await wrapper.trigger('click')
    expect(wrapper.emitted('action')![0]).toEqual(['consolidate'])
  })

  it('displays RETRY text and emits retry event when decision is retry', async () => {
    const wrapper = mount(HITLActionButton, {
      props: {
        decision: 'retry',
        disabled: false
      }
    })

    expect(wrapper.text()).toContain('RETRY / REINTENTAR')
    await wrapper.trigger('click')
    expect(wrapper.emitted('action')![0]).toEqual(['retry'])
  })

  it('handles fallback decision value gracefully', () => {
    const wrapper = mount(HITLActionButton, {
      props: {
        decision: 'unknown' as unknown as 'approve',
        disabled: false
      }
    })

    expect(wrapper.text()).toBe('ACTION')
    expect(wrapper.classes()).toContain('border-space-700')
  })
})
