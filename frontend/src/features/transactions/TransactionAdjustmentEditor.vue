<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { saveTransactionAdjustment } from '../../api/transactions';
import type { TransactionRow } from '../../api/contracts';
import { formatDate, formatMoney, formatSourceAmount } from '../../shared/format';
import { UiButton, UiDialog, UiField, UiInput } from '../../shared/ui';

const props = defineProps<{ transaction: TransactionRow | null }>();
const emit = defineEmits<{
  close: [];
  saved: [message: { title: string; detail: string }];
}>();

const kind = ref<'full' | 'partial'>('full');
const amount = ref('');
const date = ref('');
const note = ref('');
const saving = ref(false);
const error = ref('');
const removeConfirmed = ref(false);

const personalAmount = computed(() => {
  const charge = Number(props.transaction?.amount ?? 0);
  const reimbursed = kind.value === 'full' ? charge : Number(amount.value || 0);
  return Math.max(0, charge - Math.max(0, Math.min(charge, reimbursed)));
});

function close(): void {
  if (!saving.value) emit('close');
}

async function save(remove = false): Promise<void> {
  const item = props.transaction;
  if (!item) return;
  if (!remove && kind.value === 'partial') {
    const value = Number(amount.value);
    if (!Number.isFinite(value) || value <= 0 || value > item.amount) {
      error.value = `Enter an amount between 0.01 and ${item.amount.toFixed(2)}.`;
      return;
    }
  }
  saving.value = true;
  error.value = '';
  try {
    const response = await saveTransactionAdjustment(remove
      ? { transaction_id: item.id, remove: true }
      : {
          transaction_id: item.id,
          remove: false,
          reimbursed_amount: kind.value === 'full' ? item.amount : Number(amount.value),
          reimbursement_date: date.value,
          note: note.value,
        });
    if (remove) {
      item.adjustment_type = null;
      item.reimbursed_amount = null;
      item.reimbursement_date = null;
      item.reimbursement_note = null;
    } else {
      item.adjustment_type = response.adjustment_type ?? null;
      item.reimbursed_amount = response.reimbursed_amount ?? null;
      item.reimbursement_date = date.value || null;
      item.reimbursement_note = note.value.trim() || null;
    }
    item.personal_amount = response.personal_amount;
    emit('saved', {
      title: remove ? 'Adjustment removed' : 'Reimbursement saved',
      detail: remove ? `${response.merchant_raw} counts at its original amount again.` : `Personal amount: ${formatMoney(response.personal_amount)}`,
    });
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : 'Could not save spending adjustment';
  } finally {
    saving.value = false;
  }
}

function requestRemoval(): void {
  if (!removeConfirmed.value) {
    removeConfirmed.value = true;
    return;
  }
  void save(true);
}

watch(() => props.transaction, (transaction) => {
  if (!transaction) return;
  kind.value = transaction.adjustment_type === 'partial_reimbursement' ? 'partial' : 'full';
  amount.value = String(transaction.adjustment_type ? transaction.reimbursed_amount ?? transaction.amount : transaction.amount);
  date.value = transaction.reimbursement_date ?? '';
  note.value = transaction.reimbursement_note ?? '';
  error.value = '';
  removeConfirmed.value = false;
});
</script>

<template>
  <UiDialog :open="Boolean(transaction)" title-id="transaction-adjustment-title" close-label="Close spending adjustment" size="wide" @request-close="close">
    <template #header><h2 id="transaction-adjustment-title">Mark as reimbursed</h2><p>Keep the original card charge while correcting personal-spending statistics.</p></template>
    <template v-if="transaction">
        <div class="transaction-editor-snapshot"><div><span>Merchant</span><strong>{{ transaction.merchant_display_name || transaction.merchant_raw }}</strong><small>{{ transaction.merchant_raw }}</small></div><div><span>Purchase date</span><strong>{{ transaction.transaction_date ? formatDate(transaction.transaction_date) : '—' }}</strong></div><div><span>Card</span><strong>{{ transaction.provider.toUpperCase() }} •• {{ transaction.card_last4 }}</strong></div><div><span>Card charge</span><strong>{{ formatSourceAmount(transaction.amount, transaction.charged_currency) }}</strong></div></div>
        <div class="transaction-adjustment-kinds"><label :class="{ active: kind === 'full' }"><input v-model="kind" type="radio" value="full"><span><strong>Fully reimbursed</strong><small>None of this charge counts as personal spending.</small></span></label><label :class="{ active: kind === 'partial' }"><input v-model="kind" type="radio" value="partial"><span><strong>Partially reimbursed</strong><small>Only the unreimbursed remainder counts as personal spending.</small></span></label></div>
        <div class="transaction-adjustment-fields"><UiField for-id="transaction-reimbursed-amount" label="Reimbursed amount"><UiInput id="transaction-reimbursed-amount" v-model="amount" type="number" min="0.01" :max="transaction.amount" step="0.01" :disabled="kind === 'full' || saving" /></UiField><UiField for-id="transaction-reimbursement-date" label="Reimbursement date" optional><UiInput id="transaction-reimbursement-date" v-model="date" type="date" :disabled="saving" /></UiField><UiField class="wide" for-id="transaction-reimbursement-note" label="Note" optional><UiInput id="transaction-reimbursement-note" v-model="note" maxlength="500" placeholder="For example: paid for another person" :disabled="saving" /></UiField></div>
        <p class="transaction-adjustment-explanation"><b>i</b><span>The original charge remains {{ formatSourceAmount(transaction.amount, transaction.charged_currency) }}. Personal amount after this adjustment: <strong>{{ formatMoney(personalAmount) }}</strong>.</span></p>
        <p v-if="error" class="transaction-editor-error" role="alert">{{ error }}</p>
    </template>
    <template #footer><UiButton v-if="transaction?.adjustment_type" variant="danger" :disabled="saving" @click="requestRemoval">{{ removeConfirmed ? 'Confirm removal' : 'Remove adjustment' }}</UiButton><span class="transaction-editor-footer-spacer" /><UiButton :disabled="saving" @click="close">Cancel</UiButton><UiButton variant="primary" :busy="saving" @click="save(false)">{{ saving ? 'Saving…' : 'Save adjustment' }}</UiButton></template>
  </UiDialog>
</template>
