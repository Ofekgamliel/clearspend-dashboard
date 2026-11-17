import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import UiField from '../../src/shared/ui/UiField.vue';
import UiInput from '../../src/shared/ui/UiInput.vue';
import UiSelect from '../../src/shared/ui/UiSelect.vue';

describe('shared fields', () => {
  it('associates the label, description and error with a native input', async () => {
    const wrapper = mount({
      components: { UiField, UiInput },
      data: () => ({ value: '' }),
      template: `<UiField for-id="name" label="Name" description="Public label" error="Required" v-slot="ids"><UiInput id="name" v-model="value" :aria-describedby="[ids.descriptionId,ids.errorId].filter(Boolean).join(' ')" invalid /></UiField>`,
    });
    expect(wrapper.get('label').attributes('for')).toBe('name');
    expect(wrapper.get('input').attributes('aria-describedby')).toBe('name-description name-error');
    await wrapper.get('input').setValue('Synthetic event');
    expect((wrapper.vm as unknown as { value: string }).value).toBe('Synthetic event');
  });

  it('updates a native select through v-model', async () => {
    const wrapper = mount({ components: { UiSelect }, data: () => ({ value: 'planned' }), template: `<UiSelect v-model="value"><option value="planned">Planned</option><option value="active">Active</option></UiSelect>` });
    await wrapper.get('select').setValue('active');
    expect((wrapper.vm as unknown as { value: string }).value).toBe('active');
  });
});
