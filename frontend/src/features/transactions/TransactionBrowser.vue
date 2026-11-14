<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { getEvents } from '../../api/events';
import { getTransactions, saveTransactionEvent } from '../../api/transactions';
import type { AvailableEvent, PeriodKey, TransactionRow } from '../../api/contracts';
import { formatDate, formatInteger, formatMoney } from '../../shared/format';
import { modalFocus as vModalFocus } from '../../shared/modalFocus';
import {
  groupTransactionsByMerchant,
  nextMerchantGroupSort,
  sortMerchantGroups,
  transactionColumns,
  type MerchantGroupSort,
  type MerchantGroupSortKey,
  type TransactionActivityOptions,
  type TransactionMerchantGroup,
  type TransactionSort,
} from './model';
import TransactionAdjustmentEditor from './TransactionAdjustmentEditor.vue';
import TransactionCategoryEditor from './TransactionCategoryEditor.vue';
import TransactionDetailTable from './TransactionDetailTable.vue';

const props = defineProps<{ period: PeriodKey; month: string; card: string; periodLabel: string }>();
const emit = defineEmits<{ financialDataChange: [] }>();

const modalOpen = ref(false);
const search = ref('');
const rows = ref<TransactionRow[]>([]);
const total = ref(0);
const detailLoading = ref(false);
const detailError = ref('');
const detailSort = ref<TransactionSort>({ key: 'transaction_date', direction: 'desc' });
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
const activeCategoryTransaction = ref<TransactionRow | null>(null);
const activeAdjustmentTransaction = ref<TransactionRow | null>(null);
let requestId = 0;
let searchTimer: ReturnType<typeof setTimeout> | undefined;
let noticeTimer: ReturnType<typeof setTimeout> | undefined;

const merchantGroups = computed(() => sortMerchantGroups(groupTransactionsByMerchant(rows.value), groupSort.value));
const scopeLabel = computed(() => search.value.trim()
  ? `Complete-history search · sorted by ${transactionColumns.find(([key]) => key === detailSort.value.key)?.[1] ?? 'Transaction date'} ${detailSort.value.direction === 'asc' ? 'ascending' : 'descending'}`
  : activityIds.value.length
    ? `${formatInteger(rows.value.length)} linked transactions`
    : activityCategory.value && groupedMode.value
      ? 'Grouped by approved merchant name and category · select a merchant to expand'
      : `Sorted by ${transactionColumns.find(([key]) => key === detailSort.value.key)?.[1] ?? 'Transaction date'} ${detailSort.value.direction === 'asc' ? 'ascending' : 'descending'} · ${total.value > rows.value.length ? 'up to 1,000 rows' : 'all matching rows'}`);

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
    availableEvents.value = (await getEvents({ period: props.period, month: props.month, card: props.card })).available_events;
  } catch (caught) {
    eventOptionsError.value = caught instanceof Error ? caught.message : 'Could not load event choices';
  }
}

function showNotice(title: string, detail: string, error = false): void {
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
    showNotice(response.event_id ? 'Event assigned' : 'Event assignment removed', response.event_name ?? item.merchant_display_name ?? item.merchant_raw);
  } catch (caught) {
    select.value = previous;
    showNotice('Event was not updated', caught instanceof Error ? caught.message : 'Could not update event assignment', true);
  } finally {
    const pending = new Set(savingEventIds.value);
    pending.delete(item.id);
    savingEventIds.value = pending;
  }
}

function openAdjustmentEditor(item: TransactionRow): void {
  if (item.amount > 0) activeAdjustmentTransaction.value = item;
}

function handleEditorSaved(message: { title: string; detail: string }, reload = false): void {
  activeCategoryTransaction.value = null;
  activeAdjustmentTransaction.value = null;
  emit('financialDataChange');
  showNotice(message.title, message.detail);
  if (reload) void loadTransactions();
}

function reset(options: TransactionActivityOptions): void {
  search.value = options.search ?? '';
  activityIds.value = options.transactionIds ?? [];
  activityCategory.value = options.category ?? '';
  activityRoutine.value = Boolean(options.routine);
  activityTitle.value = options.title ?? 'Related transactions';
  groupedMode.value = Boolean(options.grouped);
  detailSort.value = { key: 'transaction_date', direction: 'desc' };
  expandedGroups.value = new Set();
  modalOpen.value = true;
  void loadTransactions();
  void loadAvailableEvents();
}

function open(): void { reset({ title: 'All transactions' }); }
function openActivity(options: TransactionActivityOptions): void { reset(options); }

function close(): void {
  activeCategoryTransaction.value = null;
  activeAdjustmentTransaction.value = null;
  modalOpen.value = false;
  requestId += 1;
}

function handleKeydown(event: KeyboardEvent): void {
  if (event.key !== 'Escape') return;
  if (activeCategoryTransaction.value) activeCategoryTransaction.value = null;
  else if (activeAdjustmentTransaction.value) activeAdjustmentTransaction.value = null;
  else if (modalOpen.value) close();
}

watch(search, () => {
  if (!modalOpen.value) return;
  clearTimeout(searchTimer);
  searchTimer = setTimeout(loadTransactions, 250);
});
watch([() => props.period, () => props.month, () => props.card], () => {
  if (modalOpen.value) { void loadTransactions(); void loadAvailableEvents(); }
});
onMounted(() => document.addEventListener('keydown', handleKeydown));
onBeforeUnmount(() => {
  clearTimeout(searchTimer);
  clearTimeout(noticeTimer);
  document.removeEventListener('keydown', handleKeydown);
});
defineExpose({ open, openActivity });
</script>

<template>
  <Teleport to="body">
    <div v-if="modalOpen" class="transactions-modal-backdrop" role="presentation" @mousedown.self="close">
      <section v-modal-focus class="transactions-modal" role="dialog" aria-modal="true" aria-labelledby="transactions-modal-title">
        <button type="button" class="transactions-modal-close" aria-label="Close transactions" @click="close">×</button>
        <header class="transactions-modal-head">
          <h2 id="transactions-modal-title">{{ activityTitle }}</h2>
          <p>{{ periodLabel }} · {{ card === 'all' ? 'All cards' : 'Selected card' }}</p>
          <label class="transactions-search"><span aria-hidden="true">⌕</span><input v-model="search" type="search" placeholder="Search every merchant, display name or category…" autocomplete="off"></label>
        </header>
        <div class="transactions-modal-summary">
          <div><strong>{{ search.trim() ? `${formatInteger(rows.length)} matches` : groupedMode ? `${formatInteger(rows.length)} transactions · ${formatInteger(merchantGroups.length)} merchants` : `${formatInteger(total)} transactions` }}</strong><span>{{ scopeLabel }}</span></div>
          <div v-if="activityCategory" class="transaction-view-toggle" role="group" aria-label="Transaction presentation"><button type="button" :class="{ active: groupedMode }" :aria-pressed="groupedMode" @click="groupedMode = true">By merchant</button><button type="button" :class="{ active: !groupedMode }" :aria-pressed="!groupedMode" @click="groupedMode = false">Individual</button></div>
        </div>
        <div v-if="detailError" class="transactions-detail-state error-state" role="alert"><span>{{ detailError }}</span><button type="button" @click="loadTransactions">Try again</button></div>
        <div v-else-if="detailLoading && !rows.length" class="transactions-detail-state" role="status">Loading transactions…</div>
        <div v-else-if="groupedMode" class="transactions-detail-table grouped-transaction-table" :aria-busy="detailLoading">
          <table>
            <thead><tr>
              <th :aria-sort="groupSortAria('merchant')"><button type="button" @click="groupSort = nextMerchantGroupSort(groupSort, 'merchant')">Merchant <span aria-hidden="true">{{ groupSortIcon('merchant') }}</span></button></th>
              <th :aria-sort="groupSortAria('transactions')"><button type="button" @click="groupSort = nextMerchantGroupSort(groupSort, 'transactions')">Transactions <span aria-hidden="true">{{ groupSortIcon('transactions') }}</span></button></th>
              <th :aria-sort="groupSortAria('latest_date')"><button type="button" @click="groupSort = nextMerchantGroupSort(groupSort, 'latest_date')">Latest purchase <span aria-hidden="true">{{ groupSortIcon('latest_date') }}</span></button></th>
              <th :aria-sort="groupSortAria('cards')"><button type="button" @click="groupSort = nextMerchantGroupSort(groupSort, 'cards')">Cards used <span aria-hidden="true">{{ groupSortIcon('cards') }}</span></button></th>
              <th class="right" :aria-sort="groupSortAria('amount')"><button type="button" @click="groupSort = nextMerchantGroupSort(groupSort, 'amount')">Personal spending <span aria-hidden="true">{{ groupSortIcon('amount') }}</span></button></th>
              <th class="group-expand-heading"><span class="sr-only">Expand</span></th>
            </tr></thead>
            <tbody>
              <template v-for="group in merchantGroups" :key="group.key">
                <tr class="merchant-group-row" :class="{ expanded: expandedGroups.has(group.key) }" tabindex="0" :aria-expanded="expandedGroups.has(group.key)" @click="toggleGroup(group)" @keydown.enter.prevent="toggleGroup(group)" @keydown.space.prevent="toggleGroup(group)">
                  <td><strong>{{ group.display_name }}</strong><small>{{ group.aliases.length }} original {{ group.aliases.length === 1 ? 'name' : 'names' }}</small></td><td>{{ formatInteger(group.count) }}</td><td>{{ group.latest_date ? formatDate(group.latest_date) : '—' }}</td><td>{{ group.cards.join(' · ') }}</td><td class="right"><strong>{{ formatMoney(group.amount) }}</strong></td><td><button type="button" class="group-expand-button" :aria-expanded="expandedGroups.has(group.key)" :aria-label="`${expandedGroups.has(group.key) ? 'Collapse' : 'Expand'} ${group.display_name}`" @click.stop="toggleGroup(group)">{{ expandedGroups.has(group.key) ? '⌃' : '⌄' }}</button></td>
                </tr>
                <tr v-if="expandedGroups.has(group.key)" class="merchant-group-detail-row"><td colspan="6"><div class="merchant-group-detail"><p>All transaction source details included in {{ group.display_name }}.</p><TransactionDetailTable compact :rows="group.transactions" :available-events="availableEvents" :event-options-error="eventOptionsError" :saving-event-ids="savingEventIds" @assign-event="assignEvent" @edit-category="activeCategoryTransaction = $event" @edit-adjustment="openAdjustmentEditor" /></div></td></tr>
              </template>
              <tr v-if="!merchantGroups.length"><td colspan="6" class="transactions-empty">No matching transactions.</td></tr>
            </tbody>
          </table>
          <span v-if="detailLoading" class="transactions-refreshing" role="status">Updating…</span>
        </div>
        <div v-else class="transactions-detail-table" :aria-busy="detailLoading"><TransactionDetailTable v-model:sort="detailSort" :rows="rows" :available-events="availableEvents" :event-options-error="eventOptionsError" :saving-event-ids="savingEventIds" @assign-event="assignEvent" @edit-category="activeCategoryTransaction = $event" @edit-adjustment="openAdjustmentEditor" /><span v-if="detailLoading" class="transactions-refreshing" role="status">Updating…</span></div>
      </section>
    </div>
  </Teleport>
  <TransactionCategoryEditor :transaction="activeCategoryTransaction" @close="activeCategoryTransaction = null" @saved="handleEditorSaved($event, true)" />
  <TransactionAdjustmentEditor :transaction="activeAdjustmentTransaction" @close="activeAdjustmentTransaction = null" @saved="handleEditorSaved($event)" />
  <Teleport to="body"><div v-if="transactionNotice" class="transaction-save-notice" :class="{ error: transactionNotice.error }" :role="transactionNotice.error ? 'alert' : 'status'"><span><strong>{{ transactionNotice.title }}</strong><small>{{ transactionNotice.detail }}</small></span><button type="button" aria-label="Dismiss transaction message" @click="transactionNotice = null">×</button></div></Teleport>
</template>
