import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import UiSkeleton from '../../src/shared/ui/UiSkeleton.vue';

describe('UiSkeleton', () => {
  it('is decorative and uses the requested finite shape', () => {
    const wrapper = mount(UiSkeleton, { props: { shape: 'line' } });
    expect(wrapper.attributes('aria-hidden')).toBe('true');
    expect(wrapper.classes()).toContain('ui-skeleton--line');
    expect(wrapper.attributes('role')).toBeUndefined();
  });

  it('defaults to a generic block without accessible content', () => {
    const wrapper = mount(UiSkeleton);
    expect(wrapper.classes()).toContain('ui-skeleton--block');
    expect(wrapper.text()).toBe('');
  });
});
