<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { getEvents } from '../../api/events';
import { getMerchantReference } from '../../api/merchants';
import { getTransactions, saveTransactionAdjustment, saveTransactionCategory, saveTransactionEvent } from '../../api/transactions';
import type { AvailableEvent, PeriodKey, RecentTransaction, TransactionRow } from '../../api/contracts';
import { formatDate, formatInteger, formatMoney, formatMonth } from '../../shared/format';
import {
  groupTransactionsByMerchant,
  nextMerchantGroupSort,
  nextSort,
  reportingSourceLabel,
  sortMerchantGroups,
  sortTransactions,
  transactionColumns,
  type MerchantGroupSort,
  type MerchantGroupSortKey,
  type TransactionMerchantGroup,
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
const emit = defineEmits<{ financialDataChange: [] }>();

const modalOpen = ref(false);
const search = ref('');
const rows = ref<TransactionRow[]>([]);
const total = ref(0);
const detailLoading = ref(false);
const detailError = ref('');
const sort = ref<TransactionSort>({ key: 'transaction_date', direction: 'desc' });
const activityIds = ref<number[]>([]);
const activityCategory = ref('');
const activityRoutine = ref(false);
const activityTitle = ref('All transactions');
const groupedMode = ref(false);
const groupSort = ref<MerchantGroupSort>({ key: 'latest_date', direction: 'desc' });
const expandedGroups = ref(new Set<string>());
const availableEvents = ref<AvailableEvent[]>([]);
const eventOptionsError = ref('');
const savingEventIds = ref(new Set<number>());
const transactionNotice = ref<{ title: string; detail: string; error: boolean } | null>(null);
const categoryEditorOpen = ref(false);
const activeTransaction = ref<TransactionRow | null>(null);
const categoryChoices = ref<string[]>([]);
const selectedCategory = ref('');
const categoryLoading = ref(false);
const categorySaving = ref(false);
const categoryError = ref('');
const adjustmentEditorOpen = ref(false);
const activeAdjustment = ref<TransactionRow | null>(null);
const adjustmentKind = ref<'full' | 'partial'>('full');
const adjustmentAmount = ref('');
const adjustmentDate = ref('');
const adjustmentNote = ref('');
const adjustmentSaving = ref(false);
const adjustmentError = ref('');
const adjustmentRemoveConfirmed = ref(false);
let requestId = 0;
let searchTimer: ReturnType<typeof setTimeout> | undefined;
let noticeTimer: ReturnType<typeof setTimeout> | undefined;

const sortedRows = computed(() => sortTransactions(rows.value, sort.value));
const merchantGroups = computed(() => sortMerchantGroups(groupTransactionsByMerchant(rows.value), groupSort.value));
const categoryEditorChoices = computed(() => [...new Set([
  ...categoryChoices.value,
  activeTransaction.value?.category ?? '',
])].filter(Boolean).sort((left, right) => left.localeCompare(right)));
const adjustmentPersonalAmount = computed(() => {
  const charge = Number(activeAdjustment.value?.amount ?? 0);
  const reimbursed = adjustmentKind.value === 'full' ? charge : Number(adjustmentAmount.value || 0);
  return Math.max(0, charge - Math.max(0, Math.min(charge, reimbursed)));
});
const scopeLabel = computed(() => search.value.trim()
  ? 'Complete-history search within the selected filters'
  : activityIds.value.length
    ? `${formatInteger(rows.value.length)} linked transactions`
    : activityCategory.value
      ? `${formatInteger(total.value)} transactions in ${activityCategory.value}`
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

function groupSortAria(key: MerchantGroupSortKey): 'ascending' | 'descending' | 'none' {
  if (groupSort.value.key !== key) return 'none';
  return groupSort.value.direction === 'asc' ? 'ascending' : 'descending';
}

function groupSortIcon(key: MerchantGroupSortKey): string {
  if (groupSort.value.key !== key) return '↕';
  return groupSort.value.direction === 'asc' ? '↑' : '↓';
}

function toggleGroup(group: TransactionMerchantGroup): void {
  const next = new Set(expandedGroups.value);
  if (next.has(group.key)) next.delete(group.key); else next.add(group.key);
  expandedGroups.value = next;
}

function groupRows(group: TransactionMerchantGroup): TransactionRow[] {
  return sortTransactions(group.transactions, sort.value);
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
      category: activityCategory.value,
      eventScope: activityRoutine.value ? 'routine' : 'all',
    });
    if (currentRequest !== requestId) return;
    rows.value = activityIds.value.length
      ? response.transactions.filter((item) => activityIds.value.includes(item.id))
      : response.transactions;
    total.value = activityIds.value.length ? rows.value.length : response.total;
  } catch (caught) {
    if (currentRequest !== requestId) return;
    detailError.value = caught instanceof Error ? caught.message : 'Could not load transactions';
  } finally {
    if (currentRequest === requestId) detailLoading.value = false;
  }
}

async function loadAvailableEvents(): Promise<void> {
  eventOptionsError.value = '';
  try {
    const response = await getEvents({ period: props.period, month: props.month, card: props.card });
    availableEvents.value = response.available_events;
  } catch (caught) {
    eventOptionsError.value = caught instanceof Error ? caught.message : 'Could not load event choices';
  }
}

function showTransactionNotice(title: string, detail: string, error = false): void {
  clearTimeout(noticeTimer);
  transactionNotice.value = { title, detail, error };
  noticeTimer = setTimeout(() => { transactionNotice.value = null; }, 4000);
}

async function assignEvent(item: TransactionRow, domEvent: Event): Promise<void> {
  const select = domEvent.currentTarget as HTMLSelectElement;
  const previous = item.event_id === null ? '' : String(item.event_id);
  const eventId = select.value;
  savingEventIds.value = new Set([...savingEventIds.value, item.id]);
  try {
    const response = await saveTransactionEvent({ transaction_id: item.id, event_id: eventId });
    item.event_id = response.event_id;
    item.event_name = response.event_name;
    item.event_type = response.event_type;
    item.event_destination = response.event_destination;
    emit('financialDataChange');
    showTransactionNotice(
      response.event_id ? 'Event assigned' : 'Event assignment removed',
      response.event_name ?? item.merchant_display_name ?? item.merchant_raw,
    );
  } catch (caught) {
    select.value = previous;
    showTransactionNotice('Event was not updated', caught instanceof Error ? caught.message : 'Could not update event assignment', true);
  } finally {
    const pending = new Set(savingEventIds.value);
    pending.delete(item.id);
    savingEventIds.value = pending;
  }
}

async function openCategoryEditor(item: TransactionRow): Promise<void> {
  activeTransaction.value = item;
  selectedCategory.value = item.category;
  categoryError.value = '';
  categoryEditorOpen.value = true;
  if (categoryChoices.value.length) return;
  categoryLoading.value = true;
  try {
    const response = await getMerchantReference();
    categoryChoices.value = response.categories;
  } catch (caught) {
    categoryError.value = caught instanceof Error ? caught.message : 'Could not load category choices';
  } finally {
    categoryLoading.value = false;
  }
}

function closeCategoryEditor(): void {
  if (categorySaving.value) return;
  categoryEditorOpen.value = false;
  activeTransaction.value = null;
  categoryError.value = '';
}

async function saveCategoryCorrection(): Promise<void> {
  const item = activeTransaction.value;
  const category = selectedCategory.value.trim();
  if (!item || !category) return;
  if (category === item.category && item.category_source !== 'transaction_override') {
    categoryError.value = 'Choose a different category for this transaction.';
    return;
  }
  categorySaving.value = true;
  categoryError.value = '';
  try {
    const response = await saveTransactionCategory({ transaction_id: item.id, category, subcategory: '' });
    item.category = response.category;
    item.subcategory = response.subcategory;
    item.category_source = 'transaction_override';
    categoryEditorOpen.value = false;
    activeTransaction.value = null;
    emit('financialDataChange');
    showTransactionNotice('Transaction corrected', `${response.merchant_raw} · ${response.category}`);
    await loadTransactions();
  } catch (caught) {
    categoryError.value = caught instanceof Error ? caught.message : 'Could not save category correction';
  } finally {
    categorySaving.value = false;
  }
}

function openAdjustmentEditor(item: TransactionRow): void {
  if (item.amount <= 0) return;
  activeAdjustment.value = item;
  adjustmentKind.value = item.adjustment_type === 'partial_reimbursement' ? 'partial' : 'full';
  adjustmentAmount.value = String(item.adjustment_type ? item.reimbursed_amount ?? item.amount : item.amount);
  adjustmentDate.value = item.reimbursement_date ?? '';
  adjustmentNote.value = item.reimbursement_note ?? '';
  adjustmentError.value = '';
  adjustmentRemoveConfirmed.value = false;
  adjustmentEditorOpen.value = true;
}

function closeAdjustmentEditor(): void {
  if (adjustmentSaving.value) return;
  adjustmentEditorOpen.value = false;
  activeAdjustment.value = null;
  adjustmentError.value = '';
  adjustmentRemoveConfirmed.value = false;
}

async function saveAdjustment(remove = false): Promise<void> {
  const item = activeAdjustment.value;
  if (!item) return;
  if (!remove && adjustmentKind.value === 'partial') {
    const value = Number(adjustmentAmount.value);
    if (!Number.isFinite(value) || value <= 0 || value > item.amount) {
      adjustmentError.value = `Enter an amount between 0.01 and ${item.amount.toFixed(2)}.`;
      return;
    }
  }
  adjustmentSaving.value = true;
  adjustmentError.value = '';
  try {
    const response = await saveTransactionAdjustment(remove
      ? { transaction_id: item.id, remove: true }
      : {
          transaction_id: item.id,
          remove: false,
          reimbursed_amount: adjustmentKind.value === 'full' ? item.amount : Number(adjustmentAmount.value),
          reimbursement_date: adjustmentDate.value,
          note: adjustmentNote.value,
        });
    if (remove) {
      item.adjustment_type = null;
      item.reimbursed_amount = null;
      item.reimbursement_date = null;
      item.reimbursement_note = null;
    } else {
      item.adjustment_type = response.adjustment_type ?? null;
      item.reimbursed_amount = response.reimbursed_amount ?? null;
      item.reimbursement_date = adjustmentDate.value || null;
      item.reimbursement_note = adjustmentNote.value.trim() || null;
    }
    item.personal_amount = response.personal_amount;
    adjustmentEditorOpen.value = false;
    activeAdjustment.value = null;
    emit('financialDataChange');
    showTransactionNotice(
      remove ? 'Adjustment removed' : 'Reimbursement saved',
      remove ? `${response.merchant_raw} counts at its original amount again.` : `Personal amount: ${formatMoney(response.personal_amount)}`,
    );
  } catch (caught) {
    adjustmentError.value = caught instanceof Error ? caught.message : 'Could not save spending adjustment';
  } finally {
    adjustmentSaving.value = false;
  }
}

function requestAdjustmentRemoval(): void {
  if (!adjustmentRemoveConfirmed.value) {
    adjustmentRemoveConfirmed.value = true;
    return;
  }
  void saveAdjustment(true);
}

function openModal(): void {
  search.value = '';
  activityIds.value = [];
  activityCategory.value = '';
  activityRoutine.value = false;
  activityTitle.value = 'All transactions';
  groupedMode.value = false;
  expandedGroups.value = new Set();
  modalOpen.value = true;
  void loadTransactions();
  void loadAvailableEvents();
}

function openActivity(options: { transactionIds?: number[]; search?: string; category?: string; routine?: boolean; grouped?: boolean; title?: string }): void {
  search.value = options.search ?? '';
  activityIds.value = options.transactionIds ?? [];
  activityCategory.value = options.category ?? '';
  activityRoutine.value = Boolean(options.routine);
  activityTitle.value = options.title ?? 'Related transactions';
  groupedMode.value = Boolean(options.grouped);
  expandedGroups.value = new Set();
  modalOpen.value = true;
  void loadTransactions();
  void loadAvailableEvents();
}

function closeModal(): void {
  if (categoryEditorOpen.value) closeCategoryEditor();
  if (adjustmentEditorOpen.value) closeAdjustmentEditor();
  modalOpen.value = false;
  requestId += 1;
}

function handleKeydown(event: KeyboardEvent): void {
  if (event.key !== 'Escape') return;
  if (categoryEditorOpen.value) closeCategoryEditor();
  else if (adjustmentEditorOpen.value) closeAdjustmentEditor();
  else if (modalOpen.value) closeModal();
}

watch(search, () => {
  if (!modalOpen.value) return;
  clearTimeout(searchTimer);
  searchTimer = setTimeout(loadTransactions, 250);
});

watch(
  [() => props.period, () => props.month, () => props.card],
  () => { if (modalOpen.value) { void loadTransactions(); void loadAvailableEvents(); } },
);

onMounted(() => document.addEventListener('keydown', handleKeydown));
onBeforeUnmount(() => {
  clearTimeout(searchTimer);
  clearTimeout(noticeTimer);
  document.removeEventListener('keydown', handleKeydown);
});
defineExpose({ openActivity });
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
          <h2 id="transactions-modal-title">{{ activityTitle }}</h2>
          <p>{{ periodLabel }} · {{ card === 'all' ? 'All cards' : 'Selected card' }}</p>
          <label class="transactions-search"><span aria-hidden="true">⌕</span><input v-model="search" type="search" placeholder="Search every merchant, display name or category…" autocomplete="off"></label>
        </header>
        <div class="transactions-modal-summary">
          <div><strong>{{ search.trim() ? `${formatInteger(rows.length)} matches` : `${formatInteger(total)} transactions` }}</strong><span>{{ scopeLabel }}</span></div>
          <div v-if="activityCategory" class="transaction-view-toggle" role="group" aria-label="Transaction presentation">
            <button type="button" :class="{ active: groupedMode }" :aria-pressed="groupedMode" @click="groupedMode = true">By merchant</button>
            <button type="button" :class="{ active: !groupedMode }" :aria-pressed="!groupedMode" @click="groupedMode = false">Individual</button>
          </div>
        </div>
        <div v-if="detailError" class="transactions-detail-state error-state" role="alert"><span>{{ detailError }}</span><button type="button" @click="loadTransactions">Try again</button></div>
        <div v-else-if="detailLoading && !rows.length" class="transactions-detail-state" role="status">Loading transactions…</div>
        <div v-else-if="groupedMode" class="transactions-detail-table grouped-transaction-table" :aria-busy="detailLoading">
          <table>
            <thead><tr>
              <th :aria-sort="groupSortAria('merchant')"><button type="button" @click="groupSort = nextMerchantGroupSort(groupSort, 'merchant')">Merchant <span aria-hidden="true">{{ groupSortIcon('merchant') }}</span></button></th>
              <th :aria-sort="groupSortAria('transactions')"><button type="button" @click="groupSort = nextMerchantGroupSort(groupSort, 'transactions')">Transactions <span aria-hidden="true">{{ groupSortIcon('transactions') }}</span></button></th>
              <th :aria-sort="groupSortAria('latest_date')"><button type="button" @click="groupSort = nextMerchantGroupSort(groupSort, 'latest_date')">Latest purchase <span aria-hidden="true">{{ groupSortIcon('latest_date') }}</span></button></th>
              <th class="right" :aria-sort="groupSortAria('amount')"><button type="button" @click="groupSort = nextMerchantGroupSort(groupSort, 'amount')">Personal spending <span aria-hidden="true">{{ groupSortIcon('amount') }}</span></button></th>
              <th class="group-expand-heading"><span class="sr-only">Expand</span></th>
            </tr></thead>
            <tbody>
              <template v-for="group in merchantGroups" :key="group.key">
                <tr class="merchant-group-row" :class="{ expanded: expandedGroups.has(group.key) }" tabindex="0" @click="toggleGroup(group)" @keydown.enter.prevent="toggleGroup(group)" @keydown.space.prevent="toggleGroup(group)">
                  <td><strong>{{ group.display_name }}</strong><small>{{ group.aliases.length === 1 ? group.aliases[0] : `${group.aliases.length} original names` }}</small></td>
                  <td>{{ formatInteger(group.count) }}</td>
                  <td>{{ group.latest_date ? formatDate(group.latest_date) : '—' }}</td>
                  <td class="right"><strong>{{ formatMoney(group.amount) }}</strong></td>
                  <td><button type="button" class="group-expand-button" :aria-expanded="expandedGroups.has(group.key)" :aria-label="`${expandedGroups.has(group.key) ? 'Collapse' : 'Expand'} ${group.display_name}`" @click.stop="toggleGroup(group)">{{ expandedGroups.has(group.key) ? '⌃' : '⌄' }}</button></td>
                </tr>
                <tr v-if="expandedGroups.has(group.key)" class="merchant-group-detail-row">
                  <td colspan="5">
                    <div class="merchant-group-detail">
                      <table>
                        <thead><tr>
                          <th v-for="([key, label], columnIndex) in transactionColumns" :key="key" :class="{ right: columnIndex === 6 || columnIndex === 7 }" :aria-sort="sortAria(key)"><button type="button" @click="sort = nextSort(sort, key)">{{ label }} <span aria-hidden="true">{{ sortIcon(key) }}</span></button></th>
                          <th class="transaction-action-column"><span class="sr-only">Spending adjustment</span></th>
                        </tr></thead>
                        <tbody><tr v-for="item in groupRows(group)" :key="item.id">
                          <td><strong>{{ item.merchant_raw }}</strong><small v-if="item.merchant_display_name !== item.merchant_raw">Display: {{ item.merchant_display_name }}</small><small>{{ item.merchant_normalized }}</small><i v-if="item.adjustment_type" class="transaction-reimbursement-note">{{ item.adjustment_type === 'full_reimbursement' ? 'Fully reimbursed' : `${formatMoney(item.reimbursed_amount ?? 0)} reimbursed` }}</i></td>
                          <td><span class="transaction-category-line"><span class="transaction-category-pill editable" :class="{ review: item.category === 'Needs review' }"><span>{{ item.category }}</span><button type="button" :aria-label="`Change category for ${item.merchant_display_name || item.merchant_raw}`" title="Change category for this transaction" @click.stop="openCategoryEditor(item)">✎</button></span><select class="transaction-event-select" :class="{ assigned: item.event_id, business: item.event_type === 'business_trip' }" :value="item.event_id ?? ''" :disabled="savingEventIds.has(item.id) || Boolean(eventOptionsError)" :aria-label="`${item.event_id ? 'Change' : 'Assign'} event for ${item.merchant_display_name || item.merchant_raw}`" :title="eventOptionsError || (item.event_id ? 'Change event label' : 'Assign an existing event')" @change="assignEvent(item, $event)"><option value="">{{ item.event_id ? 'No event' : '+ Event' }}</option><option v-for="event in availableEvents" :key="event.id" :value="event.id" :disabled="event.status === 'cancelled'">{{ event.name }}{{ event.status === 'cancelled' ? ' (cancelled)' : '' }}</option></select></span><i v-if="item.category_source === 'transaction_override'" class="transaction-override-note">One-off correction</i><small>{{ display(item.subcategory) }}</small></td>
                          <td><strong>{{ item.provider.toUpperCase() }} •• {{ item.card_last4 }}</strong><small>{{ display(item.source_sheet) }}</small></td>
                          <td>{{ item.transaction_date ? formatDate(item.transaction_date) : '—' }}</td><td>{{ item.billing_date ? formatDate(item.billing_date) : '—' }}</td>
                          <td><strong>{{ item.billing_month ? formatMonth(item.billing_month) : '—' }}</strong><small>{{ reportingSourceLabel(item.billing_month_source) }}<template v-if="item.installment_number"> · {{ item.installment_number }}/{{ item.installment_total ?? '?' }}</template></small></td>
                          <td class="right"><strong>{{ sourceAmount(item.amount, item.charged_currency) }}</strong><small v-if="item.adjustment_type">Personal: {{ sourceAmount(item.personal_amount, item.charged_currency) }}</small></td><td class="right">{{ sourceAmount(item.original_amount, item.original_currency) }}</td>
                          <td>{{ display(item.transaction_type) }}</td><td>{{ display(item.execution_method) }}</td><td>{{ display(item.voucher_number) }}</td><td>{{ display(item.exchange_rate) }}</td><td class="transaction-notes">{{ display(item.notes) }}</td>
                          <td class="transaction-action-column"><button type="button" class="transaction-adjustment-button" :class="{ adjusted: item.adjustment_type }" :disabled="item.amount <= 0" :aria-label="item.amount <= 0 ? 'Spending adjustment unavailable for a refund' : `${item.adjustment_type ? 'Edit reimbursement for' : 'Adjust spending for'} ${item.merchant_display_name || item.merchant_raw}`" :title="item.amount <= 0 ? 'Unavailable for refunds' : item.adjustment_type ? 'Edit reimbursement' : 'Adjust spending'" @click="openAdjustmentEditor(item)">✎</button></td>
                        </tr></tbody>
                      </table>
                    </div>
                  </td>
                </tr>
              </template>
              <tr v-if="!merchantGroups.length"><td colspan="5" class="transactions-empty">No matching transactions.</td></tr>
            </tbody>
          </table>
          <span v-if="detailLoading" class="transactions-refreshing" role="status">Updating…</span>
        </div>
        <div v-else class="transactions-detail-table" :aria-busy="detailLoading">
          <table>
            <thead><tr>
              <th v-for="([key, label], columnIndex) in transactionColumns" :key="key" :class="{ right: columnIndex === 6 || columnIndex === 7 }" :aria-sort="sortAria(key)"><button type="button" @click="sort = nextSort(sort, key)">{{ label }} <span aria-hidden="true">{{ sortIcon(key) }}</span></button></th>
              <th class="transaction-action-column"><span class="sr-only">Spending adjustment</span></th>
            </tr></thead>
            <tbody>
              <tr v-for="item in sortedRows" :key="item.id">
                <td><strong>{{ item.merchant_raw }}</strong><small v-if="item.merchant_display_name !== item.merchant_raw">Display: {{ item.merchant_display_name }}</small><small>{{ item.merchant_normalized }}</small><i v-if="item.adjustment_type" class="transaction-reimbursement-note">{{ item.adjustment_type === 'full_reimbursement' ? 'Fully reimbursed' : `${formatMoney(item.reimbursed_amount ?? 0)} reimbursed` }}</i></td>
                <td><span class="transaction-category-line"><span class="transaction-category-pill editable" :class="{ review: item.category === 'Needs review' }"><span>{{ item.category }}</span><button type="button" :aria-label="`Change category for ${item.merchant_display_name || item.merchant_raw}`" title="Change category for this transaction" @click.stop="openCategoryEditor(item)">✎</button></span><select class="transaction-event-select" :class="{ assigned: item.event_id, business: item.event_type === 'business_trip' }" :value="item.event_id ?? ''" :disabled="savingEventIds.has(item.id) || Boolean(eventOptionsError)" :aria-label="`${item.event_id ? 'Change' : 'Assign'} event for ${item.merchant_display_name || item.merchant_raw}`" :title="eventOptionsError || (item.event_id ? 'Change event label' : 'Assign an existing event')" @change="assignEvent(item, $event)"><option value="">{{ item.event_id ? 'No event' : '+ Event' }}</option><option v-for="event in availableEvents" :key="event.id" :value="event.id" :disabled="event.status === 'cancelled'">{{ event.name }}{{ event.status === 'cancelled' ? ' (cancelled)' : '' }}</option></select></span><i v-if="item.category_source === 'transaction_override'" class="transaction-override-note">One-off correction</i><small>{{ display(item.subcategory) }}</small></td>
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
                <td class="transaction-action-column"><button type="button" class="transaction-adjustment-button" :class="{ adjusted: item.adjustment_type }" :disabled="item.amount <= 0" :aria-label="item.amount <= 0 ? 'Spending adjustment unavailable for a refund' : `${item.adjustment_type ? 'Edit reimbursement for' : 'Adjust spending for'} ${item.merchant_display_name || item.merchant_raw}`" :title="item.amount <= 0 ? 'Unavailable for refunds' : item.adjustment_type ? 'Edit reimbursement' : 'Adjust spending'" @click="openAdjustmentEditor(item)">✎</button></td>
              </tr>
              <tr v-if="!sortedRows.length"><td :colspan="transactionColumns.length + 1" class="transactions-empty">No matching transactions.</td></tr>
            </tbody>
          </table>
          <span v-if="detailLoading" class="transactions-refreshing" role="status">Updating…</span>
        </div>
      </section>
    </div>
  </Teleport>
  <Teleport to="body">
    <div v-if="categoryEditorOpen && activeTransaction" class="transaction-editor-backdrop" @mousedown.self="closeCategoryEditor">
      <section class="transaction-category-editor" role="dialog" aria-modal="true" aria-labelledby="transaction-category-editor-title">
        <button type="button" class="transaction-editor-close" aria-label="Close category correction" @click="closeCategoryEditor">×</button>
        <header><h2 id="transaction-category-editor-title">Change transaction category</h2><p>This correction applies only to this transaction.</p></header>
        <div class="transaction-editor-snapshot"><div><span>Merchant</span><strong>{{ activeTransaction.merchant_display_name || activeTransaction.merchant_raw }}</strong><small>{{ activeTransaction.merchant_raw }}</small></div><div><span>Date</span><strong>{{ activeTransaction.transaction_date ? formatDate(activeTransaction.transaction_date) : '—' }}</strong></div><div><span>Card</span><strong>{{ activeTransaction.provider.toUpperCase() }} •• {{ activeTransaction.card_last4 }}</strong></div><div><span>Amount</span><strong>{{ sourceAmount(activeTransaction.amount, activeTransaction.charged_currency) }}</strong></div></div>
        <div class="transaction-category-choice"><div><span>Current category</span><strong>{{ activeTransaction.category }}</strong></div><b aria-hidden="true">→</b><label><span>New category</span><select v-model="selectedCategory" :disabled="categoryLoading || categorySaving"><option v-for="category in categoryEditorChoices" :key="category" :value="category">{{ category }}</option></select></label></div>
        <p class="transaction-category-explanation"><b>i</b><span>The merchant rule remains “{{ activeTransaction.merchant_category || activeTransaction.category }}” for other transactions and future imports. The original imported row is preserved.</span></p>
        <p v-if="categoryError" class="transaction-editor-error" role="alert">{{ categoryError }}</p>
        <footer><button type="button" class="secondary" :disabled="categorySaving" @click="closeCategoryEditor">Cancel</button><button type="button" class="primary" :disabled="categoryLoading || categorySaving || !selectedCategory" @click="saveCategoryCorrection">{{ categorySaving ? 'Saving…' : 'Save correction' }}</button></footer>
      </section>
    </div>
  </Teleport>
  <Teleport to="body">
    <div v-if="adjustmentEditorOpen && activeAdjustment" class="transaction-editor-backdrop" @mousedown.self="closeAdjustmentEditor">
      <section class="transaction-adjustment-editor" role="dialog" aria-modal="true" aria-labelledby="transaction-adjustment-title">
        <button type="button" class="transaction-editor-close" aria-label="Close spending adjustment" @click="closeAdjustmentEditor">×</button>
        <header><h2 id="transaction-adjustment-title">Mark as reimbursed</h2><p>Keep the original card charge while correcting personal-spending statistics.</p></header>
        <div class="transaction-editor-snapshot"><div><span>Merchant</span><strong>{{ activeAdjustment.merchant_display_name || activeAdjustment.merchant_raw }}</strong><small>{{ activeAdjustment.merchant_raw }}</small></div><div><span>Purchase date</span><strong>{{ activeAdjustment.transaction_date ? formatDate(activeAdjustment.transaction_date) : '—' }}</strong></div><div><span>Card</span><strong>{{ activeAdjustment.provider.toUpperCase() }} •• {{ activeAdjustment.card_last4 }}</strong></div><div><span>Card charge</span><strong>{{ sourceAmount(activeAdjustment.amount, activeAdjustment.charged_currency) }}</strong></div></div>
        <div class="transaction-adjustment-kinds"><label :class="{ active: adjustmentKind === 'full' }"><input v-model="adjustmentKind" type="radio" value="full"><span><strong>Fully reimbursed</strong><small>None of this charge counts as personal spending.</small></span></label><label :class="{ active: adjustmentKind === 'partial' }"><input v-model="adjustmentKind" type="radio" value="partial"><span><strong>Partially reimbursed</strong><small>Only the unreimbursed remainder counts as personal spending.</small></span></label></div>
        <div class="transaction-adjustment-fields"><label><span>Reimbursed amount</span><input v-model="adjustmentAmount" type="number" min="0.01" :max="activeAdjustment.amount" step="0.01" :disabled="adjustmentKind === 'full' || adjustmentSaving"></label><label><span>Reimbursement date <small>(optional)</small></span><input v-model="adjustmentDate" type="date" :disabled="adjustmentSaving"></label><label class="wide"><span>Note <small>(optional)</small></span><input v-model="adjustmentNote" maxlength="500" placeholder="For example: paid for another person" :disabled="adjustmentSaving"></label></div>
        <p class="transaction-adjustment-explanation"><b>i</b><span>The original charge remains {{ sourceAmount(activeAdjustment.amount, activeAdjustment.charged_currency) }}. Personal amount after this adjustment: <strong>{{ formatMoney(adjustmentPersonalAmount) }}</strong>.</span></p>
        <p v-if="adjustmentError" class="transaction-editor-error" role="alert">{{ adjustmentError }}</p>
        <footer><button v-if="activeAdjustment.adjustment_type" type="button" class="remove" :disabled="adjustmentSaving" @click="requestAdjustmentRemoval">{{ adjustmentRemoveConfirmed ? 'Confirm removal' : 'Remove adjustment' }}</button><span /><button type="button" class="secondary" :disabled="adjustmentSaving" @click="closeAdjustmentEditor">Cancel</button><button type="button" class="primary" :disabled="adjustmentSaving" @click="saveAdjustment(false)">{{ adjustmentSaving ? 'Saving…' : 'Save adjustment' }}</button></footer>
      </section>
    </div>
  </Teleport>
  <Teleport to="body"><div v-if="transactionNotice" class="transaction-save-notice" :class="{ error: transactionNotice.error }" :role="transactionNotice.error ? 'alert' : 'status'"><span><strong>{{ transactionNotice.title }}</strong><small>{{ transactionNotice.detail }}</small></span><button type="button" aria-label="Dismiss transaction message" @click="transactionNotice = null">×</button></div></Teleport>
</template>
