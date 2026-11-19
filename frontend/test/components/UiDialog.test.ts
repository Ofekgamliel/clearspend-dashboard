import { mount } from '@vue/test-utils';
import { afterEach, describe, expect, it } from 'vitest';
import UiDialog from '../../src/shared/ui/UiDialog.vue';

afterEach(() => { document.body.innerHTML = ''; document.body.className = ''; });

describe('UiDialog', () => {
  it('renders an accessible teleported dialog and reports close-button requests', async () => {
    const wrapper = mount(UiDialog, { attachTo: document.body, props: { open: true, titleId: 'dialog-title', descriptionId: 'dialog-description', closeLabel: 'Close dialog', size: 'compact' }, slots: { default: '<h2 id="dialog-title">Dialog</h2><p id="dialog-description">Description</p>' } });
    const dialog = document.body.querySelector('[role="dialog"]');
    expect(dialog?.getAttribute('aria-labelledby')).toBe('dialog-title');
    expect(dialog?.getAttribute('aria-describedby')).toBe('dialog-description');
    await (document.body.querySelector('[aria-label="Close dialog"]') as HTMLButtonElement).click();
    expect(wrapper.emitted('requestClose')).toEqual([['close-button']]);
    wrapper.unmount();
  });

  it('sends Escape only to the topmost open dialog', async () => {
    const first = mount(UiDialog, { props: { open: true, titleId: 'first', closeLabel: 'Close first' }, slots: { default: '<h2 id="first">First</h2>' } });
    const second = mount(UiDialog, { props: { open: true, titleId: 'second', closeLabel: 'Close second' }, slots: { default: '<h2 id="second">Second</h2>' } });
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    expect(first.emitted('requestClose')).toBeUndefined();
    expect(second.emitted('requestClose')).toEqual([['escape']]);
    first.unmount(); second.unmount();
  });

  it.each(['compact', 'medium', 'wide', 'standard', 'insight', 'large', 'browser', 'analysis', 'management'] as const)('exposes the finite %s size tier', (size) => {
    const wrapper = mount(UiDialog, { props: { open: true, titleId: `${size}-title`, closeLabel: `Close ${size}`, size }, slots: { default: `<h2 id="${size}-title">${size}</h2>` } });
    expect(document.body.querySelector('[data-ui-dialog]')?.classList.contains(`ui-dialog--${size}`)).toBe(true);
    wrapper.unmount();
  });
});
