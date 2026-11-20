<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { getObservations, saveObservationReview } from '../../api/observations';
import type { ObservationFinding, ObservationGroup, ObservationsResponse, PeriodKey } from '../../api/contracts';
import { UiButton, UiDialog } from '../../shared/ui';
import { observationActivity, observationCount, observationMetricLabels, observationMonthRange, observationReviewOption, observationReviewRequest, observationScope, observationVisual, type ObservationActivity } from './model';

const props = defineProps<{ period: PeriodKey; month: string; card: string; incomeHidden: boolean; refreshKey: number }>();
const emit = defineEmits<{ openActivity: [activity: ObservationActivity] }>();
const response = ref<ObservationsResponse | null>(null);
const loading = ref(true);
const error = ref('');
const active = ref<ObservationGroup | null>(null);
const lastReview = ref<ObservationFinding | null>(null);
const reviewedKeys = ref(new Set<string>());
const savingKey = ref('');
const reviewError = ref('');
let requestId = 0;

const modalItems = computed(() => active.value?.items ?? []);
const activeItems = computed(() => modalItems.value.filter((item) => !item.findingKey || !reviewedKeys.value.has(item.findingKey)));
const activeLabels = computed(() => active.value ? observationMetricLabels(active.value) : ['Observed value', 'Compared with', 'Result']);
const isGrouped = computed(() => modalItems.value.length > 1);
const uniqueEntities = computed(() => new Set(activeItems.value.map((item) => item.entityLabel ?? item.label)).size);
const hasPatternPeriod = computed(() => active.value?.type === 'CATEGORY ROUTINE SHIFTED');
const hasHabitKind = computed(() => active.value?.type === 'MERCHANT HABIT SHIFTED');
const groupEntityLabel = computed(() => {
  const value = active.value?.singular ?? 'merchant';
  return value.charAt(0).toUpperCase() + value.slice(1);
});
const groupEntityCountLabel = computed(() => {
  const value = active.value?.entities ?? 'merchants';
  return value.charAt(0).toUpperCase() + value.slice(1);
});
const groupedPeriodLabel = computed(() => observationMonthRange(activeItems.value.length ? activeItems.value : modalItems.value));
const modalTitle = computed(() => {
  if (!active.value || !isGrouped.value || activeItems.value.length === modalItems.value.length) return active.value?.title ?? '';
  if (!activeItems.value.length) return 'All findings reviewed';
  if (activeItems.value.length === 1) return activeItems.value[0]?.title ?? active.value.title;
  return `${activeItems.value.length} active findings`;
});

async function load(preserveUndo = false, preserveModal = false): Promise<void> {
  const current = ++requestId;
  if (!preserveModal) active.value = null;
  if (!preserveUndo) lastReview.value = null;
  loading.value = true;
  error.value = '';
  try {
    const payload = await getObservations({ period: props.period, month: props.month, card: props.card, incomeHidden: props.incomeHidden });
    if (current === requestId) response.value = payload;
  } catch (caught) {
    if (current === requestId) error.value = caught instanceof Error ? caught.message : 'Could not load financial observations';
  } finally {
    if (current === requestId) loading.value = false;
  }
}

function open(group: ObservationGroup): void { active.value = group; }
function close(): void { active.value = null; }
function evidenceLabel(item: ObservationFinding): string { return item.entityLabel ?? item.label; }
function openActivity(item: ObservationFinding): void { close(); emit('openActivity', observationActivity(item)); }

async function review(item: ObservationFinding, remove = false): Promise<void> {
  const body = observationReviewRequest(item, remove);
  if (!body) return;
  savingKey.value = item.findingKey ?? '';
  reviewError.value = '';
  try {
    await saveObservationReview(body);
    const updated = new Set(reviewedKeys.value);
    if (remove) updated.delete(item.findingKey ?? '');
    else updated.add(item.findingKey ?? '');
    reviewedKeys.value = updated;
    lastReview.value = remove ? null : item;
    const preserveModal = isGrouped.value;
    if (!preserveModal) close();
    await load(true, preserveModal);
  } catch (caught) {
    reviewError.value = caught instanceof Error ? caught.message : 'Could not save the observation review';
  } finally {
    savingKey.value = '';
  }
}

watch([() => props.period, () => props.month, () => props.card, () => props.incomeHidden, () => props.refreshKey], () => { void load(); }, { immediate: true });
</script>

<template>
  <article class="observations-panel-preview" :class="{ compact: response && !response.findingCount }" aria-labelledby="observations-preview-title" :aria-busy="loading">
    <header class="observations-head-preview">
      <div><div class="observations-title-line-preview"><h2 id="observations-preview-title">{{ response?.historical ? 'Financial patterns' : 'Financial observations' }}</h2><span v-if="response && !response.findingCount">{{ response.historical ? 'No lasting patterns' : 'No observations' }}</span></div><p v-if="response?.findingCount && response.historical">{{ observationScope(response) }}</p><p v-else-if="!response">Checking the selected period against your local history…</p></div>
      <strong v-if="response?.findingCount">{{ observationCount(response) }}</strong>
    </header>
    <div v-if="error && !response" class="observations-state-preview error-state"><span>{{ error }}</span><button type="button" @click="load()">Try again</button></div>
    <div v-else-if="response?.groups.length" class="observations-grid-preview">
      <button v-for="group in response.groups" :key="group.type" type="button" class="observation-card-preview" :class="{ priority: observationVisual(group.type).priority }" :style="{ '--observation-color': observationVisual(group.type).color }" @click="open(group)">
        <span class="observation-type-preview"><i aria-hidden="true">{{ observationVisual(group.type).icon }}</i>{{ group.type }}</span>
        <h3 dir="auto">{{ group.title }}</h3><p>{{ group.description }}</p>
        <div v-if="group.cardComparison" class="observation-comparison-preview"><b>{{ group.cardComparison.primary }}</b><span>{{ group.cardComparison.secondary }}</span></div>
        <div v-else-if="group.compactCategories?.length" class="observation-categories-preview"><span v-for="item in group.compactCategories" :key="item.label"><b dir="auto">{{ item.label }}</b><em>{{ item.result }}</em></span></div>
        <span v-else-if="group.merchantPreview" class="observation-merchants-preview" dir="auto">{{ group.merchantPreview }}</span>
        <footer v-if="group.cardSummary"><strong>{{ group.cardSummary }}</strong></footer>
      </button>
    </div>
    <div v-else-if="!response" class="observations-state-preview">Analyzing local financial activity…</div>
    <span v-if="loading && response" class="observations-updating-preview">Updating…</span>
  </article>

  <UiDialog :open="Boolean(active)" title-id="observation-preview-modal-title" close-label="Close observation details" size="insight" @request-close="close">
    <template v-if="active" #header><div class="observation-modal-head-preview" :style="{ '--observation-color': observationVisual(active.type).color }"><span><i aria-hidden="true" />{{ active.type }}</span><h2 id="observation-preview-modal-title">{{ modalTitle }}</h2><p>{{ active.description }}</p></div></template>
    <template v-if="active">
    <div class="observation-modal-body-preview">
      <div class="observation-metrics-preview">
        <div><span>{{ isGrouped ? 'Findings' : activeLabels[0] }}</span><strong>{{ isGrouped ? activeItems.length : active.value }}</strong></div>
        <div><span>{{ isGrouped ? groupEntityCountLabel : activeLabels[1] }}</span><strong>{{ isGrouped ? uniqueEntities : (active.comparison ?? 'Selected-period history') }}</strong></div>
        <div><span>{{ isGrouped && (hasPatternPeriod || hasHabitKind) ? 'Start dates' : isGrouped ? 'Period' : activeLabels[2] }}</span><strong>{{ isGrouped ? groupedPeriodLabel : (active.result ?? 'Review') }}</strong></div>
      </div>
      <section v-if="active.ruleText" class="observation-rule-preview"><strong>Why this appeared</strong><p>{{ active.ruleText }}</p></section>
      <section class="observation-findings-preview"><div><h3>{{ isGrouped ? 'Related findings' : active.type === 'POSSIBLE DUPLICATE' ? 'Matching transactions' : 'Calculation & source evidence' }}</h3><span v-if="isGrouped">{{ activeItems.length }} active · {{ modalItems.length - activeItems.length }} reviewed</span></div>
        <div v-if="!isGrouped" class="observation-single-detail-preview">
          <span v-if="activeItems[0]?.eventLabel" class="observation-event-preview">Event · {{ activeItems[0].eventLabel }}</span>
          <div v-if="activeItems[0]?.comparisonDetail" class="observation-method-preview"><span>How the comparison was calculated</span><strong>{{ activeItems[0].comparisonDetail }}</strong></div>
          <details class="observation-source-preview"><summary>Source evidence ({{ activeItems[0]?.evidence.length ?? 0 }})</summary><div><p v-for="(evidence,index) in activeItems[0]?.evidence ?? []" :key="index"><span>Source {{ index + 1 }}</span><strong dir="auto">{{ evidence }}</strong></p><p v-if="!activeItems[0]?.evidence.length"><span>Source</span><strong>No additional source rows</strong></p></div></details>
        </div>
        <div v-else class="observation-findings-table-preview" :class="{ 'with-period': hasPatternPeriod, 'with-habit': hasHabitKind, scrollable: modalItems.length > 5 }" role="table">
          <div class="observation-findings-header-preview"><span>{{ groupEntityLabel }}</span><span v-if="hasPatternPeriod">Pattern period</span><span v-if="hasHabitKind">Pattern</span><span>{{ activeLabels[0] }}</span><span>{{ activeLabels[1] }}</span><span>{{ activeLabels[2] }}</span><span /></div>
          <template v-for="item in modalItems" :key="`${item.type}:${item.findingKey ?? item.month}:${item.label}`">
            <div v-if="item.findingKey && reviewedKeys.has(item.findingKey)" class="observation-resolved-row-preview"><span><strong dir="auto">{{ evidenceLabel(item) }}</strong><small>{{ observationReviewOption(item.type)?.resolved }}</small></span><button type="button" :disabled="savingKey === item.findingKey" @click="review(item,true)">Undo</button></div>
            <details v-else class="observation-finding-row-preview">
              <summary><span><strong dir="auto">{{ evidenceLabel(item) }}</strong><small>{{ item.entitySublabel ?? item.month }}</small></span><b v-if="hasPatternPeriod">{{ item.patternPeriod ?? item.month }}</b><b v-if="hasHabitKind">{{ item.habitKind ?? 'Merchant activity changed' }}</b><b>{{ item.value }}</b><b>{{ item.comparison ?? 'Selected-period history' }}</b><b>{{ item.result ?? 'Review' }}</b><i>›</i></summary>
              <div><span v-if="item.eventLabel" class="observation-event-preview">Event · {{ item.eventLabel }}</span><div class="observation-method-preview"><span>Comparison method</span><strong>{{ item.comparisonDetail ?? 'See the rule and source evidence for this finding.' }}</strong></div><details class="observation-source-preview"><summary>Source evidence ({{ item.evidence.length }})</summary><div><p v-for="(evidence,index) in item.evidence" :key="index"><span>Source {{ index + 1 }}</span><strong dir="auto">{{ evidence }}</strong></p><p v-if="!item.evidence.length"><span>Source</span><strong>No additional source rows</strong></p></div></details><div class="observation-actions-preview"><button v-if="observationReviewOption(item.type) && item.findingKey" type="button" class="observation-review-button-preview" :disabled="savingKey === item.findingKey" @click="review(item)">{{ savingKey === item.findingKey ? 'Saving…' : observationReviewOption(item.type)?.action }}</button><button type="button" class="observation-activity-button-preview" @click="openActivity(item)">{{ observationActivity(item).label }}</button></div></div>
            </details>
          </template>
        </div>
      </section>
      <p v-if="reviewError && active" class="observation-review-error-preview">{{ reviewError }}</p>
    </div></template>
    <template v-if="active && !isGrouped && activeItems[0]" #footer><UiButton v-if="observationReviewOption(activeItems[0].type) && activeItems[0].findingKey" variant="soft-accent" size="compact" :busy="savingKey === activeItems[0].findingKey" @click="review(activeItems[0])">{{ savingKey === activeItems[0].findingKey ? 'Saving…' : observationReviewOption(activeItems[0].type)?.action }}</UiButton><UiButton variant="primary" size="compact" @click="openActivity(activeItems[0])">{{ observationActivity(activeItems[0]).label }}</UiButton></template>
  </UiDialog>
  <Teleport to="body"><div v-if="lastReview" class="observation-undo-preview" role="status"><span><strong>{{ observationReviewOption(lastReview.type)?.resolved }}</strong><small dir="auto">{{ lastReview.label }}</small></span><button type="button" :disabled="Boolean(savingKey)" @click="review(lastReview,true)">Undo</button><button type="button" aria-label="Dismiss review confirmation" @click="lastReview = null">×</button></div><div v-else-if="reviewError && !active" class="observation-undo-preview error" role="alert"><span><strong>Review could not be updated</strong><small>{{ reviewError }}</small></span><button type="button" aria-label="Dismiss error" @click="reviewError = ''">×</button></div></Teleport>
</template>
