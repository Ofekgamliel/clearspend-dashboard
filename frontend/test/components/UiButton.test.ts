import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import UiButton from '../../src/shared/ui/UiButton.vue';

describe('UiButton',()=>{
  it('defaults to a regular secondary non-submit action',()=>{const w=mount(UiButton,{slots:{default:'Continue'}});expect(w.get('button').attributes('type')).toBe('button');expect(w.get('button').classes()).toEqual(expect.arrayContaining(['ui-button--secondary','ui-button--regular']));expect(w.text()).toContain('Continue')});
  it('supports submit and semantic variants',()=>{const w=mount(UiButton,{props:{type:'submit',variant:'primary'}});expect(w.get('button').attributes('type')).toBe('submit');expect(w.get('button').classes()).toContain('ui-button--primary')});
  it('supports compact soft-accent contextual actions',()=>{const w=mount(UiButton,{props:{variant:'soft-accent',size:'compact'}});expect(w.get('button').classes()).toEqual(expect.arrayContaining(['ui-button--soft-accent','ui-button--compact']))});
  it('keeps accessible text and blocks activation while busy',async()=>{const w=mount(UiButton,{props:{busy:true},slots:{default:'Save changes'}});const b=w.get('button');expect(b.attributes('aria-busy')).toBe('true');expect(b.attributes()).toHaveProperty('disabled');expect(b.text()).toContain('Save changes');await b.trigger('click');expect(w.emitted('click')).toBeUndefined()});
});
