import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import UiIconButton from '../../src/shared/ui/UiIconButton.vue';

describe('UiIconButton', () => {
  it('requires and renders an accessible label', () => {
    const wrapper = mount(UiIconButton, { props: { label: 'Close editor', size: 'compact' }, slots: { default: '×' } });
    expect(wrapper.get('button').attributes('aria-label')).toBe('Close editor');
    expect(wrapper.get('button').attributes('type')).toBe('button');
    expect(wrapper.get('button').classes()).toContain('ui-icon-button--compact');
  });
});
