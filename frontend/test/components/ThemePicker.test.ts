import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import ThemePicker from '../../src/features/theme/ThemePicker.vue';
import { themes } from '../../src/features/theme/theme';

describe('ThemePicker', () => {
  it('opens an accessible single-select palette menu', async () => {
    const wrapper = mount(ThemePicker, { props: { modelValue: 'current' } });
    const trigger = wrapper.get('button[aria-haspopup="menu"]');

    expect(trigger.attributes('aria-expanded')).toBe('false');
    await trigger.trigger('click');

    expect(trigger.attributes('aria-expanded')).toBe('true');
    expect(wrapper.get('[role="menu"]').attributes('aria-label')).toBe('Dashboard color schemes');
    expect(wrapper.findAll('[role="menuitemradio"]')).toHaveLength(themes.length);
    expect(wrapper.get('[role="menuitemradio"][aria-checked="true"]').text()).toContain('Current');
  });

  it('emits the selected theme and restores focus to the trigger', async () => {
    const wrapper = mount(ThemePicker, { attachTo: document.body, props: { modelValue: 'current' } });
    const trigger = wrapper.get<HTMLButtonElement>('button[aria-haspopup="menu"]');
    await trigger.trigger('click');
    await wrapper.get('[role="menuitemradio"]:nth-child(2)').trigger('click');

    expect(wrapper.emitted('update:modelValue')).toEqual([['clay']]);
    expect(wrapper.find('[role="menu"]').exists()).toBe(false);
    expect(document.activeElement).toBe(trigger.element);
    wrapper.unmount();
  });

  it('supports keyboard opening, navigation, and escape dismissal', async () => {
    const wrapper = mount(ThemePicker, { attachTo: document.body, props: { modelValue: 'clay' } });
    const trigger = wrapper.get<HTMLButtonElement>('button[aria-haspopup="menu"]');
    await trigger.trigger('keydown', { key: 'ArrowDown' });

    const options = wrapper.findAll<HTMLButtonElement>('[role="menuitemradio"]');
    expect(document.activeElement).toBe(options[1].element);
    await options[1].trigger('keydown', { key: 'ArrowDown' });
    expect(document.activeElement).toBe(options[2].element);
    await options[2].trigger('keydown', { key: 'Escape' });

    expect(wrapper.find('[role="menu"]').exists()).toBe(false);
    expect(document.activeElement).toBe(trigger.element);
    wrapper.unmount();
  });
});
