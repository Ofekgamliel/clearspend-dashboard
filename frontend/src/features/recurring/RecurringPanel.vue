<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { getMerchantReference, manageRecurringProfile } from '../../api/merchants';
import { getRecurring, saveRecurringProfile } from '../../api/recurring';
import type { InstallmentCommitment, MerchantRecord, MerchantReferenceResponse, PeriodKey, RecurringResponse, RecurringSeries } from '../../api/contracts';
import { formatInteger, formatMoney, formatPercent, formatShortMonth } from '../../shared/format';
import { burdenShares, nextRecurringSort, recurringCadenceOptions, recurringProfilePayload, recurringStatusClass, recurringStatusLabels, recurringTypeOptions, sortRecurring, type RecurringSort, type RecurringSortKey, type RecurringTab } from './model';
import { filterRecurringMerchants, merchantRecurringVerdict, recurringManagementDraft, recurringManagementError, recurringManagementPayload, type RecurringManagementDraft, type RecurringVerdictFilter } from './management';

const props = defineProps<{ period: PeriodKey; month: string; card: string; refreshKey: number }>();
const emit = defineEmits<{ financialDataChange: [] }>();
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
const savingField = ref('');
const saveError = ref('');
const saveNotice = ref('');
const lifecycleDraft = ref('active');
const endMonthDraft = ref('');
const lifecycleSaving = ref(false);
const managementOpen = ref(false);
const managementData = ref<MerchantReferenceResponse | null>(null);
const managementLoading = ref(false);
const managementError = ref('');
const managementSearch = ref('');
const managementFilter = ref<RecurringVerdictFilter>('all');
const managedMerchantId = ref('');
const managedDraft = ref<RecurringManagementDraft | null>(null);
const managementSaving = ref(false);
const removeConfirm = ref(false);
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
const selectedSeriesItem = computed<RecurringSeries | null>(() => {
  const item = selectedItem.value;
  return item && 'series_id' in item ? item : null;
});
const lifecycleChanged = computed(() => {
  const item = selectedSeriesItem.value;
  if (!item) return false;
  const effectiveEnd = lifecycleDraft.value === 'ended' ? endMonthDraft.value : '';
  return lifecycleDraft.value !== item.lifecycle_status || effectiveEnd !== (item.end_month ?? '');
});
const historyMaximum = computed(() => Math.max(...(selectedItem.value?.history ?? []).map((item) => Number(item.amount ?? 0)), 1));
const remainingBalance = computed(() => (modal.value?.commitments ?? []).reduce((sum, item) => sum + item.remaining, 0));
const filteredManagedMerchants = computed(() => filterRecurringMerchants(
  managementData.value?.merchants ?? [], managementSearch.value, managementFilter.value,
));
const managedMerchant = computed<MerchantRecord | null>(() => managementData.value?.merchants.find(
  (item) => item.canonical_group_id === managedMerchantId.value,
) ?? null);

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
function openActivity(tab: 'series' | 'commitments' = 'series', seriesId = ''): void {
  openModal(tab);
  if (tab === 'series') selectedSeries.value = seriesId;
}
function closeModal(): void { modalOpen.value = false; modalRequest += 1; }
async function loadManagement(selectId = managedMerchantId.value): Promise<void> {
  managementLoading.value = true;
  managementError.value = '';
  try {
    managementData.value = await getMerchantReference();
    const next = managementData.value.merchants.find((item) => item.canonical_group_id === selectId) ?? null;
    managedMerchantId.value = next?.canonical_group_id ?? '';
    managedDraft.value = next ? recurringManagementDraft(next) : null;
  } catch (caught) {
    managementError.value = caught instanceof Error ? caught.message : 'Could not load recurring merchants';
  } finally {
    managementLoading.value = false;
  }
}
function openManagement(): void {
  closeModal();
  managementOpen.value = true;
  managementSearch.value = '';
  managementFilter.value = 'all';
  removeConfirm.value = false;
  void loadManagement();
}
function closeManagement(): void { if (!managementSaving.value) managementOpen.value = false; }
function selectManagedMerchant(merchant: MerchantRecord): void {
  managedMerchantId.value = merchant.canonical_group_id;
  managedDraft.value = recurringManagementDraft(merchant);
  managementError.value = '';
  removeConfirm.value = false;
}
function toggleManagedAlias(alias: string, included: boolean): void {
  if (!managedDraft.value) return;
  const aliases = new Set(managedDraft.value.included_aliases);
  if (included) aliases.add(alias); else aliases.delete(alias);
  managedDraft.value.included_aliases = [...aliases];
}
function changeManagedLifecycle(value: string): void {
  if (!managedDraft.value) return;
  managedDraft.value.lifecycle_status = value;
  if (value === 'ended' && !managedDraft.value.end_month) {
    managedDraft.value.end_month = props.month || panel.value?.period.end?.slice(0, 7) || '';
  }
}
async function saveManagedProfile(verdict: 'recurring' | 'not_recurring'): Promise<void> {
  const merchant = managedMerchant.value;
  const draft = managedDraft.value;
  if (!merchant || !draft || managementSaving.value) return;
  if (verdict === 'recurring') {
    const validation = recurringManagementError(draft);
    if (validation) { managementError.value = validation; return; }
  }
  managementSaving.value = true;
  managementError.value = '';
  try {
    await manageRecurringProfile(recurringManagementPayload(merchant, draft, verdict));
    await Promise.all([loadManagement(merchant.canonical_group_id), loadPanel()]);
    emit('financialDataChange');
    removeConfirm.value = false;
    saveNotice.value = verdict === 'recurring'
      ? `${merchant.display_name} is now tracked as recurring.`
      : `${merchant.display_name} is no longer tracked as recurring.`;
  } catch (caught) {
    managementError.value = caught instanceof Error ? caught.message : 'Could not update recurring decision';
  } finally {
    managementSaving.value = false;
  }
}
function selectSeries(item: RecurringSeries): void { selectedSeries.value = selectedSeries.value === item.series_id ? '' : item.series_id; }
function selectCommitment(item: InstallmentCommitment): void { const key = commitmentKey(item); selectedCommitment.value = selectedCommitment.value === key ? '' : key; }
async function updateProfile(item: RecurringSeries, field: 'recurring_type' | 'cadence', value: string): Promise<void> {
  if (value === item[field] || savingField.value) return;
  savingField.value = `${item.series_id}:${field}`;
  saveError.value = '';
  saveNotice.value = '';
  try {
    await saveRecurringProfile(recurringProfilePayload(item, { [field]: value }));
    await Promise.all([loadPanel(), loadModal()]);
    emit('financialDataChange');
    saveNotice.value = `${item.display_name} recurring profile updated.`;
  } catch (caught) {
    saveError.value = caught instanceof Error ? caught.message : 'Could not update recurring profile';
    await loadModal();
  } finally {
    savingField.value = '';
  }
}
function changeLifecycle(value: string): void {
  lifecycleDraft.value = value;
  if (value === 'ended' && !endMonthDraft.value) {
    endMonthDraft.value = selectedSeriesItem.value?.end_month
      || props.month
      || modal.value?.period.end?.slice(0, 7)
      || '';
  }
}
async function saveLifecycle(): Promise<void> {
  const item = selectedSeriesItem.value;
  if (!item || lifecycleSaving.value || !lifecycleChanged.value) return;
  if (lifecycleDraft.value === 'ended' && !endMonthDraft.value) {
    saveError.value = 'Choose an end month for an ended profile.';
    return;
  }
  lifecycleSaving.value = true;
  saveError.value = '';
  saveNotice.value = '';
  try {
    await saveRecurringProfile(recurringProfilePayload(item, {
      lifecycle_status: lifecycleDraft.value,
      end_month: lifecycleDraft.value === 'ended' ? endMonthDraft.value : '',
    }));
    await Promise.all([loadPanel(), loadModal()]);
    emit('financialDataChange');
    saveNotice.value = lifecycleDraft.value === 'ended'
      ? `${item.display_name} will no longer be expected after ${endMonthDraft.value}.`
      : `${item.display_name} lifecycle updated.`;
  } catch (caught) {
    saveError.value = caught instanceof Error ? caught.message : 'Could not update recurring lifecycle';
    await loadModal();
  } finally {
    lifecycleSaving.value = false;
  }
}
function handleKeydown(event: KeyboardEvent): void {
  if (event.key !== 'Escape') return;
  if (managementOpen.value) closeManagement(); else if (modalOpen.value) closeModal();
}

watch([() => props.period, () => props.month, () => props.card, () => props.refreshKey], loadPanel, { immediate: true });
watch(modalPeriod, () => { selectedSeries.value = ''; selectedCommitment.value = ''; void loadModal(); });
watch(() => props.card, () => { if (modalOpen.value) void loadModal(); });
watch(selectedSeriesItem, (item) => {
  lifecycleDraft.value = item?.lifecycle_status ?? 'active';
  endMonthDraft.value = item?.end_month ?? '';
  saveError.value = '';
});
onMounted(() => document.addEventListener('keydown', handleKeydown));
onBeforeUnmount(() => document.removeEventListener('keydown', handleKeydown));
defineExpose({ openActivity });
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

  <Teleport to="body"><div v-if="modalOpen" class="recurring-modal-backdrop" @mousedown.self="closeModal"><section class="recurring-modal-preview" role="dialog" aria-modal="true" aria-labelledby="recurring-modal-title"><button type="button" class="recurring-modal-close" aria-label="Close recurring details" @click="closeModal">×</button><header class="recurring-modal-head-preview"><div><p>PLANNED SPENDING</p><h2 id="recurring-modal-title">Recurring &amp; commitments</h2><span>Reviewed recurring charges, scheduled obligations, and finite installments.</span></div><button type="button" class="recurring-manage-button-preview" @click="openManagement">Manage recurring merchants</button></header><nav class="recurring-modal-toolbar"><div><button v-for="value in (['month','year','all'] as PeriodKey[])" :key="value" type="button" :class="{ active: modalPeriod === value }" @click="modalPeriod = value">{{ value === 'month' ? 'Month' : value === 'year' ? 'Latest year' : 'All time' }}</button></div><div><button v-for="value in (['series','commitments','verdicts'] as RecurringTab[])" :key="value" type="button" :class="{ active: modalTab === value }" @click="modalTab = value">{{ value === 'series' ? 'Recurring & scheduled' : value === 'commitments' ? 'Installments' : 'Verdict summary' }}</button></div></nav><div class="recurring-modal-body-preview">
      <div v-if="modalError" class="recurring-state error-state"><span>{{ modalError }}</span><button type="button" @click="loadModal">Try again</button></div><div v-else-if="modalLoading && !modal" class="recurring-state">Loading recurring details…</div>
      <template v-else-if="modal"><div v-if="modalTab === 'verdicts'" class="recurring-verdicts"><div><span>Reviewed rows</span><strong>{{ modal.verdict_summary.reviewed }}</strong><small>Reviewed recurring decisions</small></div><div><span>Recurring / obligations</span><strong>{{ modal.verdict_summary.recurring }}</strong><small>Included in recurring analysis</small></div><div><span>Not recurring</span><strong>{{ modal.verdict_summary.not_recurring }}</strong><small>Excluded from this section</small></div><div><span>Unresolved</span><strong>{{ modal.verdict_summary.unresolved }}</strong><small>No decision still required</small></div></div>
      <template v-else><div class="recurring-detail-metrics-preview"><template v-if="modalTab === 'series'"><div><span>Recurring billed</span><strong>{{ formatMoney(modal.metrics.recurring_billed) }}</strong><small>Excludes installments</small></div><div><span>Active series</span><strong>{{ modal.metrics.active_series }}</strong><small>In selected scope</small></div><div><span>Needs attention</span><strong>{{ modal.metrics.needs_attention }}</strong><small>Missing, due, or changed</small></div><div><span>Installments</span><strong>{{ formatMoney(modal.metrics.installment_billed) }}</strong><small>{{ modal.metrics.installment_plans }} plans</small></div></template><template v-else><div><span>Installment charges</span><strong>{{ formatMoney(modal.metrics.installment_billed) }}</strong><small>{{ modal.metrics.installment_plans }} plans</small></div><div><span>Monthly average</span><strong>{{ formatMoney(modal.metrics.installment_average) }}</strong><small>Actually billed</small></div><div><span>Remaining balance</span><strong>{{ formatMoney(remainingBalance) }}</strong><small>Estimated</small></div><div><span>Completed</span><strong>{{ modal.commitments.filter(item => item.status === 'completed').length }}</strong><small>Plans in scope</small></div></template></div>
      <div class="recurring-table-wrap-preview"><table v-if="modalTab === 'series'"><thead><tr><th v-for="([key,label]) in ([['display_name','Merchant'],['category','Category'],['recurring_type','Type'],['cadence','Cadence'],['amount','Amount'],['coverage','Expected / coverage'],['status','Status']] as [RecurringSortKey,string][])" :key="key" :aria-sort="sortAria(seriesSort,key)"><button type="button" @click="seriesSort = nextRecurringSort(seriesSort,key)">{{ label }} <span>{{ sortIcon(seriesSort,key) }}</span></button></th></tr></thead><tbody><tr v-for="item in sortedSeries" :key="item.series_id" :class="{ selected: selectedSeries === item.series_id }" tabindex="0" @click="selectSeries(item)" @keydown.enter="selectSeries(item)"><td><strong>{{ item.display_name }}</strong><small>{{ item.source_aliases.join(' / ') || 'Select for billing history' }}</small></td><td>{{ item.category }}</td><td @click.stop><span class="recurring-inline-select-preview"><select :value="item.recurring_type" :disabled="Boolean(savingField)" aria-label="Recurring type" @change="updateProfile(item,'recurring_type',($event.target as HTMLSelectElement).value)"><option v-for="option in recurringTypeOptions" :key="option" :value="option">{{ option }}</option></select><i aria-hidden="true" /></span></td><td @click.stop><span class="recurring-inline-select-preview"><select :value="item.cadence" :disabled="Boolean(savingField)" aria-label="Recurring cadence" @change="updateProfile(item,'cadence',($event.target as HTMLSelectElement).value)"><option v-for="option in recurringCadenceOptions" :key="option" :value="option">{{ option }}</option></select><i aria-hidden="true" /></span></td><td>{{ item.amount === null ? '—' : formatMoney(item.amount) }}</td><td>{{ item.coverage }}</td><td><i class="recurring-status-pill" :class="recurringStatusClass(item.status)">{{ statusLabel(item.status) }}</i></td></tr><tr v-if="!sortedSeries.length"><td colspan="7">No matching items.</td></tr></tbody></table>
      <table v-else><thead><tr><th v-for="([key,label]) in ([['display_name','Purchase'],['category','Category'],['current_installment','Progress'],['paid','Paid'],['remaining','Remaining'],['status','Status']] as [RecurringSortKey,string][])" :key="key" :aria-sort="sortAria(commitmentSort,key)"><button type="button" @click="commitmentSort = nextRecurringSort(commitmentSort,key)">{{ label }} <span>{{ sortIcon(commitmentSort,key) }}</span></button></th></tr></thead><tbody><tr v-for="item in sortedCommitments" :key="commitmentKey(item)" :class="{ selected: selectedCommitment === commitmentKey(item) }" tabindex="0" @click="selectCommitment(item)" @keydown.enter="selectCommitment(item)"><td><strong>{{ item.display_name }}</strong><small>{{ item.source_alias || 'Select for billing history' }}</small></td><td>{{ item.category }}</td><td>{{ item.progress }}</td><td>{{ formatMoney(item.paid) }}</td><td>{{ formatMoney(item.remaining) }}</td><td><i class="recurring-status-pill" :class="recurringStatusClass(item.status)">{{ statusLabel(item.status) }}</i></td></tr><tr v-if="!sortedCommitments.length"><td colspan="6">No matching items.</td></tr></tbody></table></div>
      <section v-if="selectedItem" class="recurring-history-inspector"><div><h3>{{ selectedItem.display_name }}</h3><p>{{ 'series_id' in selectedItem ? 'Actual charges for the reviewed recurring alias set.' : 'Billed installments for this finite plan.' }}</p><div v-if="selectedSeriesItem" class="recurring-lifecycle-editor-preview" :class="{ ended: lifecycleDraft === 'ended' }"><label><span>Lifecycle</span><span class="recurring-inline-select-preview"><select :value="lifecycleDraft" :disabled="lifecycleSaving" @change="changeLifecycle(($event.target as HTMLSelectElement).value)"><option value="active">Active</option><option value="ended">Ended</option><option value="paused">Paused</option><option value="unknown">Unknown</option></select><i aria-hidden="true" /></span></label><label v-if="lifecycleDraft === 'ended'"><span>End month</span><input v-model="endMonthDraft" type="month" :disabled="lifecycleSaving"></label><button type="button" :disabled="lifecycleSaving || !lifecycleChanged || (lifecycleDraft === 'ended' && !endMonthDraft)" @click="saveLifecycle">{{ lifecycleSaving ? 'Saving…' : lifecycleDraft === 'ended' ? 'Confirm ended lifecycle' : 'Save lifecycle' }}</button><small>{{ lifecycleDraft === 'ended' ? 'After this month, the payment is no longer expected. Transaction history stays available.' : 'Selection is local until you save it.' }}</small></div></div><div><h4>Actual billing history</h4><div class="recurring-history-bars"><span v-for="point in selectedItem.history" :key="point.month" :title="`${formatShortMonth(point.month)}: ${historyLabel(point.amount,point.state)}`"><i :class="point.state" :style="{ width: historyWidth(point.amount,point.state) }" /><b>{{ formatShortMonth(point.month) }}</b><small>{{ historyLabel(point.amount,point.state) }}</small></span></div><div class="recurring-history-legend"><span><i />Actual charge</span><span><i class="missing" />Expected but missing</span><span><i class="not-expected" />No charge expected</span></div></div></section></template></template>
      <p v-if="saveError" class="recurring-save-error-preview" role="alert">{{ saveError }}</p><span v-if="modalLoading || savingField" class="recurring-modal-updating">{{ savingField ? 'Saving…' : 'Updating…' }}</span></div></section></div></Teleport>
  <Teleport to="body"><div v-if="managementOpen" class="recurring-management-backdrop-preview" @mousedown.self="closeManagement"><section class="recurring-management-modal-preview" role="dialog" aria-modal="true" aria-labelledby="recurring-management-title"><button type="button" class="recurring-modal-close" aria-label="Close recurring management" @click="closeManagement">×</button><header><h2 id="recurring-management-title">Recurring merchant rules</h2><p>Choose exactly which original statement names belong to each recurring series.</p></header><div class="recurring-management-tools-preview"><label><span>⌕</span><input v-model="managementSearch" type="search" placeholder="Search merchant or original name"></label><select v-model="managementFilter"><option value="all">All merchants</option><option value="recurring">Recurring</option><option value="not_recurring">Not recurring</option><option value="unreviewed">Not reviewed</option></select></div><div v-if="managementError && !managementData" class="recurring-state error-state"><span>{{ managementError }}</span><button type="button" @click="loadManagement()">Try again</button></div><div v-else class="recurring-management-body-preview"><aside><div class="recurring-management-list-head-preview"><strong>{{ filteredManagedMerchants.length }} merchants</strong><span v-if="managementLoading">Updating…</span></div><div class="recurring-management-list-preview"><button v-for="merchant in filteredManagedMerchants" :key="merchant.canonical_group_id" type="button" :class="{ active: managedMerchantId === merchant.canonical_group_id }" @click="selectManagedMerchant(merchant)"><span><strong>{{ merchant.display_name }}</strong><small>{{ merchant.aliases.length }} original {{ merchant.aliases.length === 1 ? 'name' : 'names' }} · {{ merchant.transactions }} transactions</small></span><i :class="merchantRecurringVerdict(merchant)">{{ merchantRecurringVerdict(merchant) === 'recurring' ? `${merchant.aliases.filter(alias => alias.recurring_included).length}/${merchant.aliases.length} aliases` : merchantRecurringVerdict(merchant) === 'not_recurring' ? 'Not recurring' : 'Not reviewed' }}</i></button><p v-if="!filteredManagedMerchants.length">No merchants match these filters.</p></div></aside><main v-if="managedMerchant && managedDraft" class="recurring-management-editor-preview"><header><div><h3>{{ managedMerchant.display_name }}</h3><p>{{ managedMerchant.aliases.length }} original names · {{ managedMerchant.transactions }} transactions</p></div><span :class="merchantRecurringVerdict(managedMerchant)">{{ merchantRecurringVerdict(managedMerchant) === 'recurring' ? 'Recurring' : merchantRecurringVerdict(managedMerchant) === 'not_recurring' ? 'Not recurring' : 'Not reviewed' }}</span></header><section><h4>Included original names</h4><p>Only checked names contribute billing history and missing-payment expectations.</p><label v-for="alias in managedMerchant.aliases" :key="alias.merchant_normalized" class="recurring-managed-alias-preview"><input type="checkbox" :checked="managedDraft.included_aliases.includes(alias.merchant_normalized)" :disabled="managementSaving" @change="toggleManagedAlias(alias.merchant_normalized,($event.target as HTMLInputElement).checked)"><span><strong>{{ alias.merchant_raw }}</strong><small>{{ alias.category }} · {{ alias.transactions }} transactions</small></span></label></section><div class="recurring-management-fields-preview"><label><span>Type</span><select v-model="managedDraft.recurring_type" :disabled="managementSaving"><option v-for="option in recurringTypeOptions" :key="option" :value="option">{{ option }}</option></select></label><label><span>Cadence</span><select v-model="managedDraft.cadence" :disabled="managementSaving"><option v-for="option in recurringCadenceOptions" :key="option" :value="option">{{ option }}</option></select></label><label><span>Lifecycle</span><select :value="managedDraft.lifecycle_status" :disabled="managementSaving" @change="changeManagedLifecycle(($event.target as HTMLSelectElement).value)"><option value="active">Active</option><option value="paused">Paused</option><option value="ended">Ended</option><option value="unknown">Unknown</option></select></label><label v-if="managedDraft.lifecycle_status === 'ended'"><span>End month</span><input v-model="managedDraft.end_month" type="month" :disabled="managementSaving"></label></div><p v-if="managementError" class="recurring-management-error-preview" role="alert">{{ managementError }}</p><div v-if="removeConfirm" class="recurring-management-confirm-preview"><span><strong>Mark every alias as not recurring?</strong><small>Recurring monitoring and future missing-payment warnings will stop. Transactions remain available.</small></span><div><button type="button" @click="removeConfirm = false">Cancel</button><button type="button" class="danger" :disabled="managementSaving" @click="saveManagedProfile('not_recurring')">{{ managementSaving ? 'Saving…' : 'Confirm not recurring' }}</button></div></div><footer><button v-if="merchantRecurringVerdict(managedMerchant) === 'recurring'" type="button" class="danger" :disabled="managementSaving" @click="removeConfirm = true">Mark as not recurring</button><button type="button" class="primary" :disabled="managementSaving" @click="saveManagedProfile('recurring')">{{ managementSaving ? 'Saving…' : merchantRecurringVerdict(managedMerchant) === 'recurring' ? 'Save recurring settings' : 'Add to recurring tracking' }}</button></footer></main><div v-else class="recurring-management-empty-preview">Select a merchant to manage its recurring rule.</div></div></section></div></Teleport>
  <Teleport to="body"><div v-if="saveNotice" class="recurring-save-notice-preview" role="status"><span>{{ saveNotice }}</span><button type="button" aria-label="Dismiss recurring update" @click="saveNotice = ''">×</button></div></Teleport>
</template>
