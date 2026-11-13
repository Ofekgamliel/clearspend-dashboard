<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { getRecurring } from '../../api/recurring';
import type { InstallmentCommitment, PeriodKey, RecurringResponse, RecurringSeries } from '../../api/contracts';
import { formatInteger, formatMoney, formatPercent, formatShortMonth } from '../../shared/format';
import { burdenShares, nextRecurringSort, recurringStatusClass, recurringStatusLabels, sortRecurring, type RecurringSort, type RecurringSortKey, type RecurringTab } from './model';

const props = defineProps<{ period: PeriodKey; month: string; card: string }>();
const panel = ref<RecurringResponse | null>(null);
const loading = ref(true);
const error = ref('');
const modalOpen = ref(false);
const modalPeriod = ref<PeriodKey>('month');
const modalTab = ref<RecurringTab>('series');
const modal = ref<RecurringResponse | null>(null);
const modalLoading = ref(false);
const modalError = ref('');
const selectedSeries = ref('');
const selectedCommitment = ref('');
const seriesSort = ref<RecurringSort>({ key: 'display_name', direction: 'asc' });
const commitmentSort = ref<RecurringSort>({ key: 'remaining', direction: 'desc' });
let panelRequest = 0;
let modalRequest = 0;

const shares = computed(() => burdenShares(panel.value?.metrics.recurring_share ?? 0, panel.value?.metrics.installment_share ?? 0));
const sortedSeries = computed(() => sortRecurring(modal.value?.series ?? [], seriesSort.value));
const sortedCommitments = computed(() => sortRecurring(modal.value?.commitments ?? [], commitmentSort.value));
const selectedItem = computed<RecurringSeries | InstallmentCommitment | null>(() => {
  if (!modal.value) return null;
  if (modalTab.value === 'series') return modal.value.series.find((item) => item.series_id === selectedSeries.value) ?? null;
  if (modalTab.value === 'commitments') return modal.value.commitments.find((item) => commitmentKey(item) === selectedCommitment.value) ?? null;
  return null;
});
const historyMaximum = computed(() => Math.max(...(selectedItem.value?.history ?? []).map((item) => Number(item.amount ?? 0)), 1));
const remainingBalance = computed(() => (modal.value?.commitments ?? []).reduce((sum, item) => sum + item.remaining, 0));

function commitmentKey(item: InstallmentCommitment): string {
  return `${item.display_name}\u0000${item.source_alias}\u0000${item.progress}`;
}

function statusLabel(status: string): string { return recurringStatusLabels[status] ?? status; }
function previewAmount(item: RecurringSeries | InstallmentCommitment): number | null { return 'series_id' in item ? item.amount : item.charge; }
function previewDetail(item: RecurringSeries | InstallmentCommitment): string {
  if ('series_id' in item) return `${item.source_aliases.join(' / ')}${item.source_aliases.length ? ' · ' : ''}${item.recurring_type} · ${item.cadence} · ${item.coverage}`;
  return `${item.source_alias ? `${item.source_alias} · ` : ''}Installment ${item.progress} · ${item.remaining_count} remaining`;
}
function historyWidth(amount: number | null, state: string): string {
  if (amount !== null) return `${Math.max(12, amount / historyMaximum.value * 100)}%`;
  return state === 'missing' ? '38%' : '18%';
}
function historyLabel(amount: number | null, state: string): string {
  if (amount !== null) return formatMoney(amount);
  return state === 'missing' ? 'Missing' : 'No charge';
}
function sortAria(sort: RecurringSort, key: RecurringSortKey): 'ascending' | 'descending' | 'none' {
  return sort.key === key ? (sort.direction === 'asc' ? 'ascending' : 'descending') : 'none';
}
function sortIcon(sort: RecurringSort, key: RecurringSortKey): string {
  return sort.key === key ? (sort.direction === 'asc' ? '↑' : '↓') : '↕';
}

async function loadPanel(): Promise<void> {
  const current = ++panelRequest;
  loading.value = true;
  error.value = '';
  try {
    const response = await getRecurring({ period: props.period, month: props.month, card: props.card });
    if (current === panelRequest) panel.value = response;
  } catch (caught) {
    if (current === panelRequest) error.value = caught instanceof Error ? caught.message : 'Could not load recurring spending';
  } finally {
    if (current === panelRequest) loading.value = false;
  }
}

async function loadModal(): Promise<void> {
  if (!modalOpen.value) return;
  const current = ++modalRequest;
  modalLoading.value = true;
  modalError.value = '';
  try {
    const response = await getRecurring({ period: modalPeriod.value, month: props.month, card: props.card });
    if (current !== modalRequest) return;
    modal.value = response;
    if (!response.series.some((item) => item.series_id === selectedSeries.value)) selectedSeries.value = '';
    if (!response.commitments.some((item) => commitmentKey(item) === selectedCommitment.value)) selectedCommitment.value = '';
  } catch (caught) {
    if (current === modalRequest) modalError.value = caught instanceof Error ? caught.message : 'Could not load recurring spending';
  } finally {
    if (current === modalRequest) modalLoading.value = false;
  }
}

function openModal(tab: RecurringTab = 'series', item?: RecurringSeries | InstallmentCommitment): void {
  modalPeriod.value = props.period;
  modalTab.value = tab;
  modal.value = panel.value;
  selectedSeries.value = tab === 'series' && item && 'series_id' in item ? item.series_id : '';
  selectedCommitment.value = tab === 'commitments' && item && !('series_id' in item) ? commitmentKey(item) : '';
  modalOpen.value = true;
  if (!modal.value || modal.value.period.key !== modalPeriod.value) void loadModal();
}
function closeModal(): void { modalOpen.value = false; modalRequest += 1; }
function selectSeries(item: RecurringSeries): void { selectedSeries.value = selectedSeries.value === item.series_id ? '' : item.series_id; }
function selectCommitment(item: InstallmentCommitment): void { const key = commitmentKey(item); selectedCommitment.value = selectedCommitment.value === key ? '' : key; }
function handleKeydown(event: KeyboardEvent): void { if (event.key === 'Escape' && modalOpen.value) closeModal(); }

watch([() => props.period, () => props.month, () => props.card], loadPanel, { immediate: true });
watch(modalPeriod, () => { selectedSeries.value = ''; selectedCommitment.value = ''; void loadModal(); });
watch(() => props.card, () => { if (modalOpen.value) void loadModal(); });
onMounted(() => document.addEventListener('keydown', handleKeydown));
onBeforeUnmount(() => document.removeEventListener('keydown', handleKeydown));
</script>

<template>
  <article class="recurring-panel-preview" aria-labelledby="recurring-title" :aria-busy="loading">
    <header class="recurring-panel-head">
      <div><h2 id="recurring-title">Recurring &amp; commitments</h2><p v-if="panel">{{ panel.period.label }} · reviewed verdicts: {{ panel.verdict_summary.recurring }} recurring or obligations · {{ panel.verdict_summary.not_recurring }} not recurring</p><p v-else>Loading reviewed recurring profiles…</p></div>
      <button type="button" @click="openModal()">View all details →</button>
    </header>
    <div v-if="error && !panel" class="recurring-state error-state"><span>{{ error }}</span><button type="button" @click="loadPanel">Try again</button></div>
    <template v-else-if="panel">
      <div class="recurring-summary-preview">
        <div><span>Recurring billed</span><strong>{{ formatMoney(panel.metrics.recurring_billed) }}</strong><small>{{ panel.period.key === 'month' ? 'Recurring and scheduled · excludes installments' : `${panel.period.label} · excludes installments` }}</small></div>
        <div><span>{{ panel.period.key === 'month' ? 'Active series' : 'Monthly billed average' }}</span><strong>{{ panel.period.key === 'month' ? formatInteger(panel.metrics.active_series) : formatMoney(panel.metrics.recurring_average) }}</strong><small>{{ panel.period.key === 'month' ? 'Including upcoming obligations' : 'Recurring and scheduled only' }}</small></div>
        <div class="attention"><span>Needs attention</span><strong>{{ formatInteger(panel.metrics.needs_attention) }}</strong><small>Missing, due, or changed</small></div>
        <div><span>Commitments</span><strong>{{ formatMoney(panel.metrics.installment_billed) }}</strong><small>{{ panel.metrics.installment_plans }} installment plans</small></div>
      </div>
      <div class="recurring-preview-layout">
        <div class="recurring-preview-lists">
          <section class="recurring-list-card"><button type="button" class="recurring-list-title" @click="openModal('series')"><span><i /><strong>Recurring &amp; scheduled</strong></span><small>{{ panel.series.length }} total<template v-if="panel.series.length > 3"> · scroll</template></small></button><div class="recurring-list-scroll"><button v-for="item in panel.series" :key="item.series_id" type="button" class="recurring-preview-item" @click="openModal('series', item)"><span><strong>{{ item.display_name }}</strong><small>{{ previewDetail(item) }}</small></span><span><strong>{{ previewAmount(item) === null ? '—' : formatMoney(previewAmount(item) ?? 0) }}</strong><i class="recurring-status-pill" :class="recurringStatusClass(item.status)">{{ statusLabel(item.status) }}</i></span></button><p v-if="!panel.series.length">No recurring or scheduled payments in this scope.</p></div></section>
          <section class="recurring-list-card commitments"><button type="button" class="recurring-list-title" @click="openModal('commitments')"><span><i /><strong>Commitments</strong></span><small>{{ panel.commitments.length }} total<template v-if="panel.commitments.length > 3"> · scroll</template></small></button><div class="recurring-list-scroll"><button v-for="item in panel.commitments" :key="commitmentKey(item)" type="button" class="recurring-preview-item" @click="openModal('commitments', item)"><span><strong>{{ item.display_name }}</strong><small>{{ previewDetail(item) }}</small></span><span><strong>{{ formatMoney(item.charge) }}</strong><i class="recurring-status-pill" :class="recurringStatusClass(item.status)">{{ statusLabel(item.status) }}</i></span></button><p v-if="!panel.commitments.length">No installment commitments in this scope.</p></div></section>
        </div>
        <aside class="recurring-composition"><h3>Spending composition</h3><p>Share of actual spending in the selected period. Expected future charges are never included.</p><div class="recurring-composition-bar" role="img" :aria-label="`Recurring ${shares.recurring.toFixed(1)}%, installments ${shares.installments.toFixed(1)}%, other ${shares.other.toFixed(1)}%`"><i :style="{ width: `${shares.recurring}%` }" /><i class="installment" :style="{ width: `${shares.installments}%` }" /><i class="other" :style="{ width: `${shares.other}%` }" /></div><div class="recurring-composition-legend"><span><i />Recurring &amp; scheduled <strong>{{ formatPercent(shares.recurring) }}</strong></span><span><i class="installment" />Installments <strong>{{ formatPercent(shares.installments) }}</strong></span><span><i class="other" />Other spending <strong>{{ formatPercent(shares.other) }}</strong></span></div><dl><dt>Recurring average</dt><dd>{{ formatMoney(panel.metrics.recurring_average) }}</dd><dt>Installment average</dt><dd>{{ formatMoney(panel.metrics.installment_average) }}</dd><dt>Needs attention</dt><dd>{{ panel.metrics.needs_attention }}</dd></dl></aside>
      </div>
    </template>
    <div v-else class="recurring-state">Loading recurring spending…</div>
  </article>

  <Teleport to="body"><div v-if="modalOpen" class="recurring-modal-backdrop" @mousedown.self="closeModal"><section class="recurring-modal-preview" role="dialog" aria-modal="true" aria-labelledby="recurring-modal-title"><button type="button" class="recurring-modal-close" aria-label="Close recurring details" @click="closeModal">×</button><header><p>PLANNED SPENDING</p><h2 id="recurring-modal-title">Recurring &amp; commitments</h2><span>Reviewed recurring charges, scheduled obligations, and finite installments.</span></header><nav class="recurring-modal-toolbar"><div><button v-for="value in (['month','year','all'] as PeriodKey[])" :key="value" type="button" :class="{ active: modalPeriod === value }" @click="modalPeriod = value">{{ value === 'month' ? 'Month' : value === 'year' ? 'Latest year' : 'All time' }}</button></div><div><button v-for="value in (['series','commitments','verdicts'] as RecurringTab[])" :key="value" type="button" :class="{ active: modalTab === value }" @click="modalTab = value">{{ value === 'series' ? 'Recurring & scheduled' : value === 'commitments' ? 'Installments' : 'Verdict summary' }}</button></div></nav><div class="recurring-modal-body-preview">
      <div v-if="modalError" class="recurring-state error-state"><span>{{ modalError }}</span><button type="button" @click="loadModal">Try again</button></div><div v-else-if="modalLoading && !modal" class="recurring-state">Loading recurring details…</div>
      <template v-else-if="modal"><div v-if="modalTab === 'verdicts'" class="recurring-verdicts"><div><span>Reviewed rows</span><strong>{{ modal.verdict_summary.reviewed }}</strong><small>Reviewed recurring decisions</small></div><div><span>Recurring / obligations</span><strong>{{ modal.verdict_summary.recurring }}</strong><small>Included in recurring analysis</small></div><div><span>Not recurring</span><strong>{{ modal.verdict_summary.not_recurring }}</strong><small>Excluded from this section</small></div><div><span>Unresolved</span><strong>{{ modal.verdict_summary.unresolved }}</strong><small>No decision still required</small></div></div>
      <template v-else><div class="recurring-detail-metrics-preview"><template v-if="modalTab === 'series'"><div><span>Recurring billed</span><strong>{{ formatMoney(modal.metrics.recurring_billed) }}</strong><small>Excludes installments</small></div><div><span>Active series</span><strong>{{ modal.metrics.active_series }}</strong><small>In selected scope</small></div><div><span>Needs attention</span><strong>{{ modal.metrics.needs_attention }}</strong><small>Missing, due, or changed</small></div><div><span>Installments</span><strong>{{ formatMoney(modal.metrics.installment_billed) }}</strong><small>{{ modal.metrics.installment_plans }} plans</small></div></template><template v-else><div><span>Installment charges</span><strong>{{ formatMoney(modal.metrics.installment_billed) }}</strong><small>{{ modal.metrics.installment_plans }} plans</small></div><div><span>Monthly average</span><strong>{{ formatMoney(modal.metrics.installment_average) }}</strong><small>Actually billed</small></div><div><span>Remaining balance</span><strong>{{ formatMoney(remainingBalance) }}</strong><small>Estimated</small></div><div><span>Completed</span><strong>{{ modal.commitments.filter(item => item.status === 'completed').length }}</strong><small>Plans in scope</small></div></template></div>
      <div class="recurring-table-wrap-preview"><table v-if="modalTab === 'series'"><thead><tr><th v-for="([key,label]) in ([['display_name','Merchant'],['category','Category'],['recurring_type','Type'],['cadence','Cadence'],['amount','Amount'],['coverage','Expected / coverage'],['status','Status']] as [RecurringSortKey,string][])" :key="key" :aria-sort="sortAria(seriesSort,key)"><button type="button" @click="seriesSort = nextRecurringSort(seriesSort,key)">{{ label }} <span>{{ sortIcon(seriesSort,key) }}</span></button></th></tr></thead><tbody><tr v-for="item in sortedSeries" :key="item.series_id" :class="{ selected: selectedSeries === item.series_id }" tabindex="0" @click="selectSeries(item)" @keydown.enter="selectSeries(item)"><td><strong>{{ item.display_name }}</strong><small>{{ item.source_aliases.join(' / ') || 'Select for billing history' }}</small></td><td>{{ item.category }}</td><td>{{ item.recurring_type }}</td><td>{{ item.cadence }}</td><td>{{ item.amount === null ? '—' : formatMoney(item.amount) }}</td><td>{{ item.coverage }}</td><td><i class="recurring-status-pill" :class="recurringStatusClass(item.status)">{{ statusLabel(item.status) }}</i></td></tr><tr v-if="!sortedSeries.length"><td colspan="7">No matching items.</td></tr></tbody></table>
      <table v-else><thead><tr><th v-for="([key,label]) in ([['display_name','Purchase'],['category','Category'],['current_installment','Progress'],['paid','Paid'],['remaining','Remaining'],['status','Status']] as [RecurringSortKey,string][])" :key="key" :aria-sort="sortAria(commitmentSort,key)"><button type="button" @click="commitmentSort = nextRecurringSort(commitmentSort,key)">{{ label }} <span>{{ sortIcon(commitmentSort,key) }}</span></button></th></tr></thead><tbody><tr v-for="item in sortedCommitments" :key="commitmentKey(item)" :class="{ selected: selectedCommitment === commitmentKey(item) }" tabindex="0" @click="selectCommitment(item)" @keydown.enter="selectCommitment(item)"><td><strong>{{ item.display_name }}</strong><small>{{ item.source_alias || 'Select for billing history' }}</small></td><td>{{ item.category }}</td><td>{{ item.progress }}</td><td>{{ formatMoney(item.paid) }}</td><td>{{ formatMoney(item.remaining) }}</td><td><i class="recurring-status-pill" :class="recurringStatusClass(item.status)">{{ statusLabel(item.status) }}</i></td></tr><tr v-if="!sortedCommitments.length"><td colspan="6">No matching items.</td></tr></tbody></table></div>
      <section v-if="selectedItem" class="recurring-history-inspector"><div><h3>{{ selectedItem.display_name }}</h3><p>{{ 'series_id' in selectedItem ? 'Actual charges for the reviewed recurring alias set.' : 'Billed installments for this finite plan.' }}</p></div><div><h4>Actual billing history</h4><div class="recurring-history-bars"><span v-for="point in selectedItem.history" :key="point.month" :title="`${formatShortMonth(point.month)}: ${historyLabel(point.amount,point.state)}`"><i :class="point.state" :style="{ width: historyWidth(point.amount,point.state) }" /><b>{{ formatShortMonth(point.month) }}</b><small>{{ historyLabel(point.amount,point.state) }}</small></span></div><div class="recurring-history-legend"><span><i />Actual charge</span><span><i class="missing" />Expected but missing</span><span><i class="not-expected" />No charge expected</span></div></div></section></template></template>
      <span v-if="modalLoading" class="recurring-modal-updating">Updating…</span></div></section></div></Teleport>
</template>
