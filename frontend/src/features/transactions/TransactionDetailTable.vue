<script setup lang="ts">
import { computed, ref } from 'vue';
import type { AvailableEvent, TransactionRow } from '../../api/contracts';
import { formatDate, formatMoney, formatMonth, formatSourceAmount } from '../../shared/format';
import {
  nextSort,
  reportingSourceLabel,
  sortTransactions,
  transactionColumns,
  type TransactionSort,
  type TransactionSortKey,
} from './model';

const props = defineProps<{
  rows: TransactionRow[];
  availableEvents: AvailableEvent[];
  eventOptionsError: string;
  savingEventIds: Set<number>;
  compact?: boolean;
  sort?: TransactionSort;
}>();

const emit = defineEmits<{
  assignEvent: [item: TransactionRow, event: Event];
  editCategory: [item: TransactionRow];
  editAdjustment: [item: TransactionRow];
  'update:sort': [sort: TransactionSort];
}>();

const internalSort = ref<TransactionSort>({ key: 'transaction_date', direction: 'desc' });
const activeSort = computed(() => props.sort ?? internalSort.value);
const sortedRows = computed(() => sortTransactions(props.rows, activeSort.value));

function changeSort(key: TransactionSortKey): void {
  const value = nextSort(activeSort.value, key);
  if (props.sort) emit('update:sort', value); else internalSort.value = value;
}

function display(value: unknown): string {
  return value === null || value === undefined || value === '' ? '—' : String(value);
}

function sortAria(key: TransactionSortKey): 'ascending' | 'descending' | 'none' {
  if (activeSort.value.key !== key) return 'none';
  return activeSort.value.direction === 'asc' ? 'ascending' : 'descending';
}

function sortIcon(key: TransactionSortKey): string {
  if (activeSort.value.key !== key) return '↕';
  return activeSort.value.direction === 'asc' ? '↑' : '↓';
}
</script>

<template>
  <div class="transaction-source-scroll" :class="{ compact }">
  <table class="transaction-source-table">
    <thead><tr>
      <th
        v-for="([key, label], columnIndex) in transactionColumns"
        :key="key"
        :class="{ right: columnIndex === 6 || columnIndex === 7 }"
        :aria-sort="sortAria(key)"
      ><button type="button" @click="changeSort(key)">{{ label }} <span aria-hidden="true">{{ sortIcon(key) }}</span></button></th>
      <th class="transaction-action-column"><span class="sr-only">Spending adjustment</span></th>
    </tr></thead>
    <tbody>
      <tr v-for="item in sortedRows" :key="item.id">
        <td>
          <strong dir="auto">{{ item.merchant_raw }}</strong>
          <small v-if="item.merchant_display_name !== item.merchant_raw" dir="auto">Display: {{ item.merchant_display_name }}</small>
          <small dir="auto">{{ item.merchant_normalized }}</small>
          <i v-if="item.adjustment_type" class="transaction-reimbursement-note">{{ item.adjustment_type === 'full_reimbursement' ? 'Fully reimbursed' : `${formatMoney(item.reimbursed_amount ?? 0)} reimbursed` }}</i>
        </td>
        <td>
          <span class="transaction-category-line">
            <span class="transaction-category-pill editable" :class="{ review: item.category === 'Needs review' }">
              <span dir="auto">{{ item.category }}</span>
              <button type="button" :aria-label="`Change category for ${item.merchant_display_name || item.merchant_raw}`" title="Change category for this transaction" @click.stop="emit('editCategory', item)">✎</button>
            </span>
            <select
              class="transaction-event-select"
              :class="{ assigned: item.event_id, business: item.event_type === 'business_trip' }"
              :value="item.event_id ?? ''"
              :disabled="savingEventIds.has(item.id) || Boolean(eventOptionsError)"
              :aria-label="`${item.event_id ? 'Change' : 'Assign'} event for ${item.merchant_display_name || item.merchant_raw}`"
              :title="eventOptionsError || (item.event_id ? 'Change event label' : 'Assign an existing event')"
              @change="emit('assignEvent', item, $event)"
            >
              <option value="">{{ item.event_id ? 'No event' : '+ Event' }}</option>
              <option v-for="event in availableEvents" :key="event.id" :value="event.id" :disabled="event.status === 'cancelled'">{{ event.name }}{{ event.status === 'cancelled' ? ' (cancelled)' : '' }}</option>
            </select>
          </span>
          <i v-if="item.category_source === 'transaction_override'" class="transaction-override-note">One-off correction</i>
          <small dir="auto">{{ display(item.subcategory) }}</small>
        </td>
        <td><strong>{{ item.provider.toUpperCase() }} •• {{ item.card_last4 }}</strong><small>{{ display(item.source_sheet) }}</small></td>
        <td>{{ item.transaction_date ? formatDate(item.transaction_date) : '—' }}</td>
        <td>{{ item.billing_date ? formatDate(item.billing_date) : '—' }}</td>
        <td><strong>{{ item.billing_month ? formatMonth(item.billing_month) : '—' }}</strong><small>{{ reportingSourceLabel(item.billing_month_source) }}<template v-if="item.installment_number"> · {{ item.installment_number }}/{{ item.installment_total ?? '?' }}</template></small></td>
        <td dir="ltr" class="right"><strong>{{ formatSourceAmount(item.amount, item.charged_currency) }}</strong><small v-if="item.adjustment_type">Personal: {{ formatSourceAmount(item.personal_amount, item.charged_currency) }}</small></td>
        <td dir="ltr" class="right">{{ formatSourceAmount(item.original_amount, item.original_currency) }}</td>
        <td>{{ display(item.transaction_type) }}</td>
        <td>{{ display(item.execution_method) }}</td>
        <td>{{ display(item.voucher_number) }}</td>
        <td>{{ display(item.exchange_rate) }}</td>
        <td class="transaction-notes">{{ display(item.notes) }}</td>
        <td class="transaction-action-column"><button type="button" class="transaction-adjustment-button" :class="{ adjusted: item.adjustment_type }" :disabled="item.amount <= 0" :aria-label="item.amount <= 0 ? 'Spending adjustment unavailable for a refund' : `${item.adjustment_type ? 'Edit reimbursement for' : 'Adjust spending for'} ${item.merchant_display_name || item.merchant_raw}`" :title="item.amount <= 0 ? 'Unavailable for refunds' : item.adjustment_type ? 'Edit reimbursement' : 'Adjust spending'" @click="emit('editAdjustment', item)">✎</button></td>
      </tr>
      <tr v-if="!sortedRows.length"><td :colspan="transactionColumns.length + 1" class="transactions-empty">No matching transactions.</td></tr>
    </tbody>
  </table>
  </div>
</template>
