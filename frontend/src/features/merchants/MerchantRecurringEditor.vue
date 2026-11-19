<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { manageRecurringProfile } from '../../api/merchants.ts';
import type { MerchantRecord } from '../../api/contracts.ts';
import { recurringManagementDraft, recurringManagementError, recurringManagementPayload, type RecurringManagementDraft } from '../recurring/management.ts';
import { recurringCadenceOptions, recurringTypeOptions } from '../recurring/model.ts';
import { UiButton, UiField, UiInput, UiSelect } from '../../shared/ui';

const props = defineProps<{ merchant: MerchantRecord; disabled?: boolean }>();
const emit = defineEmits<{ saved: [groupId: string, message: string] }>();
const draft = ref<RecurringManagementDraft>(recurringManagementDraft(props.merchant));
const saving = ref(false);
const error = ref('');
const removeConfirm = ref(false);
const verdict = computed(() => props.merchant.recurring_profile?.verdict ?? 'unreviewed');
const includedCount = computed(() => draft.value.included_aliases.length);

watch(() => props.merchant.canonical_group_id, () => {
  draft.value = recurringManagementDraft(props.merchant);
  error.value = '';
  removeConfirm.value = false;
});
watch(() => props.merchant.recurring_profile?.updated_at, () => {
  draft.value = recurringManagementDraft(props.merchant);
});

function toggleAlias(alias: string, checked: boolean): void {
  const values = new Set(draft.value.included_aliases);
  if (checked) values.add(alias); else values.delete(alias);
  draft.value.included_aliases = [...values];
  error.value = '';
}
function changeLifecycle(value: string): void {
  draft.value.lifecycle_status = value;
  if (value !== 'ended') draft.value.end_month = '';
  error.value = '';
}
async function save(targetVerdict: 'recurring' | 'not_recurring'): Promise<void> {
  if (props.disabled || saving.value) return;
  if (targetVerdict === 'recurring') {
    error.value = recurringManagementError(draft.value);
    if (error.value) return;
  }
  saving.value = true;
  error.value = '';
  try {
    await manageRecurringProfile(recurringManagementPayload(props.merchant, draft.value, targetVerdict));
    removeConfirm.value = false;
    emit('saved', props.merchant.canonical_group_id, targetVerdict === 'recurring' ? `${props.merchant.display_name} recurring settings saved.` : `${props.merchant.display_name} marked as not recurring.`);
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : 'Could not update recurring settings';
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <section class="merchant-recurring-editor">
    <header>
      <div><h3>Recurring settings</h3><p>Choose exactly which original names belong to this recurring series.</p></div>
      <i :class="verdict">{{ verdict === 'recurring' ? 'Recurring' : verdict === 'not_recurring' ? 'Not recurring' : 'Not reviewed' }}</i>
    </header>
    <p v-if="disabled" class="merchant-recurring-lock">Apply or discard the display-name/category changes above before editing recurring settings.</p>
    <div class="merchant-recurring-alias-head"><span><strong>Included original names</strong><small>Only checked aliases affect billing history and missing-payment expectations.</small></span><b>{{ includedCount }}/{{ merchant.aliases.length }}</b></div>
    <div class="merchant-recurring-aliases">
      <label v-for="alias in merchant.aliases" :key="alias.merchant_normalized">
        <input type="checkbox" :checked="draft.included_aliases.includes(alias.merchant_normalized)" :disabled="disabled || saving" @change="toggleAlias(alias.merchant_normalized, ($event.target as HTMLInputElement).checked)">
        <span><strong>{{ alias.merchant_raw }}</strong><small>{{ alias.category }} · {{ alias.transactions }} transactions</small></span>
      </label>
    </div>
    <div class="merchant-recurring-fields">
      <UiField for-id="merchant-recurring-type" label="Type"><UiSelect id="merchant-recurring-type" v-model="draft.recurring_type" density="dense" :disabled="disabled || saving"><option v-for="option in recurringTypeOptions" :key="option" :value="option">{{ option }}</option></UiSelect></UiField>
      <UiField for-id="merchant-recurring-cadence" label="Cadence"><UiSelect id="merchant-recurring-cadence" v-model="draft.cadence" density="dense" :disabled="disabled || saving"><option v-for="option in recurringCadenceOptions" :key="option" :value="option">{{ option }}</option></UiSelect></UiField>
      <UiField for-id="merchant-recurring-lifecycle" label="Lifecycle"><UiSelect id="merchant-recurring-lifecycle" :model-value="draft.lifecycle_status" density="dense" :disabled="disabled || saving" @update:model-value="changeLifecycle"><option value="active">Active</option><option value="paused">Paused</option><option value="ended">Ended</option><option value="unknown">Unknown</option></UiSelect></UiField>
      <UiField v-if="draft.lifecycle_status === 'ended'" for-id="merchant-recurring-end" label="End month"><UiInput id="merchant-recurring-end" v-model="draft.end_month" density="dense" type="month" :disabled="disabled || saving" /></UiField>
    </div>
    <p v-if="error" class="transaction-editor-error" role="alert">{{ error }}</p>
    <div v-if="removeConfirm" class="merchant-recurring-confirm">
      <span><strong>Mark every alias as not recurring?</strong><small>Recurring monitoring and future missing-payment warnings will stop. Transactions and the saved configuration remain available.</small></span>
      <div><UiButton @click="removeConfirm = false">Cancel</UiButton><UiButton variant="danger" :busy="saving" @click="save('not_recurring')">{{ saving ? 'Saving…' : 'Confirm not recurring' }}</UiButton></div>
    </div>
    <footer>
      <UiButton v-if="verdict === 'recurring'" variant="danger" :disabled="disabled || saving" @click="removeConfirm = true">Mark as not recurring</UiButton>
      <UiButton variant="primary" :disabled="disabled" :busy="saving" @click="save('recurring')">{{ saving ? 'Saving…' : verdict === 'recurring' ? 'Save recurring settings' : 'Add to recurring tracking' }}</UiButton>
    </footer>
  </section>
</template>
