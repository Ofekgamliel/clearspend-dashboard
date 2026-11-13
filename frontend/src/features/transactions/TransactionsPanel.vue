<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { getTransactions } from '../../api/transactions';
import type { PeriodKey, RecentTransaction, TransactionRow } from '../../api/contracts';
import { formatDate, formatInteger, formatMoney, formatMonth } from '../../shared/format';
import {
  nextSort,
  reportingSourceLabel,
  sortTransactions,
  transactionColumns,
  type TransactionSort,
  type TransactionSortKey,
} from './model';

const props = defineProps<{
  recent: RecentTransaction[];
  period: PeriodKey;
  month: string;
  card: string;
  periodLabel: string;
  loading: boolean;
}>();

const modalOpen = ref(false);
const search = ref('');
const rows = ref<TransactionRow[]>([]);
const total = ref(0);
const detailLoading = ref(false);
const detailError = ref('');
const sort = ref<TransactionSort>({ key: 'transaction_date', direction: 'desc' });
let requestId = 0;
let searchTimer: ReturnType<typeof setTimeout> | undefined;

const sortedRows = computed(() => sortTransactions(rows.value, sort.value));
const scopeLabel = computed(() => search.value.trim()
  ? 'Complete-history search within the selected filters'
  : total.value > rows.value.length
    ? `Showing the newest ${formatInteger(rows.value.length)} of ${formatInteger(total.value)}`
    : `${formatInteger(total.value)} transactions`);

function reportingLabel(row: RecentTransaction): string {
  if (row.billing_date) return formatDate(row.billing_date);
  if (row.billing_month) return formatMonth(row.billing_month);
  return row.transaction_date ? formatDate(row.transaction_date) : '—';
}

function sourceAmount(value: number | null, currency: string | null): string {
  if (value === null) return '—';
  const amount = new Intl.NumberFormat('en-IL', { maximumFractionDigits: 2 }).format(value);
  return `${amount} ${currency ?? ''}`.trim();
}

function display(value: unknown): string {
  return value === null || value === undefined || value === '' ? '—' : String(value);
}

function sortAria(key: TransactionSortKey): 'ascending' | 'descending' | 'none' {
  if (sort.value.key !== key) return 'none';
  return sort.value.direction === 'asc' ? 'ascending' : 'descending';
}

function sortIcon(key: TransactionSortKey): string {
  if (sort.value.key !== key) return '↕';
  return sort.value.direction === 'asc' ? '↑' : '↓';
}

async function loadTransactions(): Promise<void> {
  if (!modalOpen.value) return;
  const currentRequest = ++requestId;
  detailLoading.value = true;
  detailError.value = '';
  try {
    const response = await getTransactions({
      period: props.period,
      month: props.month,
      card: props.card,
      search: search.value,
    });
    if (currentRequest !== requestId) return;
    rows.value = response.transactions;
    total.value = response.total;
  } catch (caught) {
    if (currentRequest !== requestId) return;
    detailError.value = caught instanceof Error ? caught.message : 'Could not load transactions';
  } finally {
    if (currentRequest === requestId) detailLoading.value = false;
  }
}

function openModal(): void {
  modalOpen.value = true;
  void loadTransactions();
}

function closeModal(): void {
  modalOpen.value = false;
  requestId += 1;
}

function handleKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape' && modalOpen.value) closeModal();
}

watch(search, () => {
  if (!modalOpen.value) return;
  clearTimeout(searchTimer);
  searchTimer = setTimeout(loadTransactions, 250);
});

watch(
  [() => props.period, () => props.month, () => props.card],
  () => { if (modalOpen.value) void loadTransactions(); },
);

onMounted(() => document.addEventListener('keydown', handleKeydown));
onBeforeUnmount(() => {
  clearTimeout(searchTimer);
  document.removeEventListener('keydown', handleKeydown);
});
</script>

<template>
  <article class="transactions-panel" aria-labelledby="transactions-title" :aria-busy="loading">
    <header class="transactions-head">
      <div><h2 id="transactions-title">Recent transactions</h2><p>{{ periodLabel }} · five-column summary</p></div>
      <button type="button" class="transactions-view-all" @click="openModal">View all transactions →</button>
    </header>
    <div class="recent-table-wrap">
      <table class="recent-transactions-table">
        <thead><tr><th>Merchant</th><th>Category</th><th>Card</th><th>Reporting period</th><th class="right">Amount</th></tr></thead>
        <tbody>
          <tr v-for="(item, index) in recent" :key="`${item.provider}-${item.card_last4}-${item.transaction_date}-${index}`">
            <td><span class="recent-merchant-icon" :class="{ refund: item.amount < 0 }">{{ item.merchant_raw.trim().charAt(0).toUpperCase() || '?' }}</span><span><strong>{{ item.merchant_raw }}</strong><small>{{ item.provider.toUpperCase() }} statement</small></span></td>
            <td><span class="transaction-category-pill" :class="{ review: item.category === 'Needs review' }">{{ item.category }}</span><small v-if="item.subcategory">{{ item.subcategory }}</small></td>
            <td><strong>{{ item.provider.toUpperCase() }} •• {{ item.card_last4 }}</strong></td>
            <td><strong>{{ reportingLabel(item) }}</strong><small>{{ reportingSourceLabel(item.billing_month_source) }}</small></td>
            <td class="right" :class="{ charge: item.amount >= 0, refund: item.amount < 0 }">{{ item.amount < 0 ? '+' : '−' }}{{ formatMoney(Math.abs(item.amount)) }}</td>
          </tr>
          <tr v-if="!recent.length"><td colspan="5" class="transactions-empty">No transactions found.</td></tr>
        </tbody>
      </table>
    </div>
  </article>

  <Teleport to="body">
    <div v-if="modalOpen" class="transactions-modal-backdrop" role="presentation" @mousedown.self="closeModal">
      <section class="transactions-modal" role="dialog" aria-modal="true" aria-labelledby="transactions-modal-title">
        <button type="button" class="transactions-modal-close" aria-label="Close transactions" @click="closeModal">×</button>
        <header class="transactions-modal-head">
          <h2 id="transactions-modal-title">All transactions</h2>
          <p>{{ periodLabel }} · {{ card === 'all' ? 'All cards' : 'Selected card' }}</p>
          <label class="transactions-search"><span aria-hidden="true">⌕</span><input v-model="search" type="search" placeholder="Search every merchant, display name or category…" autocomplete="off"></label>
        </header>
        <div class="transactions-modal-summary"><strong>{{ search.trim() ? `${formatInteger(rows.length)} matches` : `${formatInteger(total)} transactions` }}</strong><span>{{ scopeLabel }}</span></div>
        <div v-if="detailError" class="transactions-detail-state error-state" role="alert"><span>{{ detailError }}</span><button type="button" @click="loadTransactions">Try again</button></div>
        <div v-else-if="detailLoading && !rows.length" class="transactions-detail-state" role="status">Loading transactions…</div>
        <div v-else class="transactions-detail-table" :aria-busy="detailLoading">
          <table>
            <thead><tr>
              <th v-for="([key, label], columnIndex) in transactionColumns" :key="key" :class="{ right: columnIndex === 6 || columnIndex === 7 }" :aria-sort="sortAria(key)"><button type="button" @click="sort = nextSort(sort, key)">{{ label }} <span aria-hidden="true">{{ sortIcon(key) }}</span></button></th>
            </tr></thead>
            <tbody>
              <tr v-for="item in sortedRows" :key="item.id">
                <td><strong>{{ item.merchant_raw }}</strong><small v-if="item.merchant_display_name !== item.merchant_raw">Display: {{ item.merchant_display_name }}</small><small>{{ item.merchant_normalized }}</small></td>
                <td><span class="transaction-category-line"><span class="transaction-category-pill" :class="{ review: item.category === 'Needs review' }">{{ item.category }}</span><span v-if="item.event_name" class="transaction-event-pill" :class="{ business: item.event_type === 'business_trip' }">{{ item.event_name }}</span></span><small>{{ display(item.subcategory) }}</small></td>
                <td><strong>{{ item.provider.toUpperCase() }} •• {{ item.card_last4 }}</strong><small>{{ display(item.source_sheet) }}</small></td>
                <td>{{ item.transaction_date ? formatDate(item.transaction_date) : '—' }}</td>
                <td>{{ item.billing_date ? formatDate(item.billing_date) : '—' }}</td>
                <td><strong>{{ item.billing_month ? formatMonth(item.billing_month) : '—' }}</strong><small>{{ reportingSourceLabel(item.billing_month_source) }}<template v-if="item.installment_number"> · {{ item.installment_number }}/{{ item.installment_total ?? '?' }}</template></small></td>
                <td class="right"><strong>{{ sourceAmount(item.amount, item.charged_currency) }}</strong><small v-if="item.adjustment_type">Personal: {{ sourceAmount(item.personal_amount, item.charged_currency) }}</small></td>
                <td class="right">{{ sourceAmount(item.original_amount, item.original_currency) }}</td>
                <td>{{ display(item.transaction_type) }}</td>
                <td>{{ display(item.execution_method) }}</td>
                <td>{{ display(item.voucher_number) }}</td>
                <td>{{ display(item.exchange_rate) }}</td>
                <td class="transaction-notes">{{ display(item.notes) }}</td>
              </tr>
              <tr v-if="!sortedRows.length"><td :colspan="transactionColumns.length" class="transactions-empty">No matching transactions.</td></tr>
            </tbody>
          </table>
          <span v-if="detailLoading" class="transactions-refreshing" role="status">Updating…</span>
        </div>
      </section>
    </div>
  </Teleport>
</template>
