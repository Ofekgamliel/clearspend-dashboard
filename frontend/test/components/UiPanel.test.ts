import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import UiPanel from '../../src/shared/ui/UiPanel.vue';

describe('UiPanel', () => {
  it('preserves caller-owned heading relationships and content', () => {
    const wrapper = mount(UiPanel, {
      attrs: { 'aria-labelledby': 'synthetic-title' },
      slots: { header: '<header><h2 id="synthetic-title">Synthetic panel</h2></header>', default: '<p>Panel content</p>' },
    });
    expect(wrapper.element.tagName).toBe('ARTICLE');
    expect(wrapper.attributes('aria-labelledby')).toBe('synthetic-title');
    expect(wrapper.get('h2').text()).toBe('Synthetic panel');
  });

  it('supports a section root and compact density without guessing hierarchy', () => {
    const wrapper = mount(UiPanel, { props: { as: 'section', density: 'compact' } });
    expect(wrapper.element.tagName).toBe('SECTION');
    expect(wrapper.classes()).toContain('ui-panel--compact');
  });
});
