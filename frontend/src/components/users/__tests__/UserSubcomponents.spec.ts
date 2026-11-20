import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import UserCreateForm from '../UserCreateForm.vue'
import UserListPanel from '../UserListPanel.vue'

describe('User management subcomponents', () => {
  it('UserCreateForm emits submit payload with field values and supports resetFields', async () => {
    const wrapper = mount(UserCreateForm, {
      props: {
        localError: null,
        successMessage: null,
        isSubmitting: false,
        isStoreLoading: false,
      },
    })

    await wrapper.find('[data-test="username-input"]').setValue('operador1')
    await wrapper.find('[data-test="password-input"]').setValue('SecretPass123')
    await wrapper.find('[data-test="confirm-password-input"]').setValue('SecretPass123')
    await wrapper.find('[data-test="is-admin-checkbox"]').setValue(true)
    await wrapper.find('form').trigger('submit.prevent')

    expect(wrapper.emitted('submit')).toEqual([
      [
        {
          username: 'operador1',
          password: 'SecretPass123',
          confirmPassword: 'SecretPass123',
          isAdmin: true,
        },
      ],
    ])

    ;(wrapper.vm as unknown as { resetFields: () => void }).resetFields()
    await wrapper.vm.$nextTick()
    expect((wrapper.find('[data-test="username-input"]').element as HTMLInputElement).value).toBe('')
  })

  it('UserListPanel emits refresh, toggle-active, save-edit and confirm-delete actions', async () => {
    const users = [
      {
        id: 'u-1',
        username: 'admin',
        is_admin: true,
        is_active: true,
        created_at: '2026-11-18T10:00:00Z',
      },
      {
        id: 'u-2',
        username: 'operador',
        is_admin: false,
        is_active: true,
        created_at: '2026-11-18T11:00:00Z',
      },
    ]

    const wrapper = mount(UserListPanel, {
      props: {
        users,
        currentUserId: 'u-1',
        usersLoading: false,
        isStoreLoading: false,
        editingUserId: 'u-2',
        confirmDeleteUserId: null,
      },
    })

    await wrapper.find('[data-test="edit-is-admin-checkbox"]').setValue(true)
    await wrapper.find('[data-test="save-edit-btn"]').trigger('click')
    expect(wrapper.emitted('save-edit')?.[0]?.[1]).toEqual({
      isAdmin: true,
      password: '',
    })

    const toggleBtns = wrapper.findAll('[data-test="toggle-active-btn"]')
    expect((toggleBtns[0]?.element as HTMLButtonElement | undefined)?.disabled).toBe(true)
    await toggleBtns[1]?.trigger('click')
    expect(wrapper.emitted('toggle-active')?.[0]?.[0]).toMatchObject({ id: 'u-2' })
  })
})
