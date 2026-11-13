<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { getObservations, saveObservationReview } from '../../api/observations';
import type { ObservationFinding, ObservationGroup, ObservationsResponse, PeriodKey } from '../../api/contracts';
import { observationActivity, observationCount, observationMetricLabels, observationReviewOption, observationReviewRequest, observationScope, observationVisual, type ObservationActivity } from './model';

const props = defineProps<{ period: PeriodKey; month: string; card: string; incomeHidden: boolean; refreshKey: number }>();
const emit = defineEmits<{ openActivity: [activity: ObservationActivity] }>();
const response = ref<ObservationsResponse | null>(null);
const loading = ref(true);
const error = ref('');
const active = ref<ObservationGroup | null>(null);
const lastReview = ref<ObservationFinding | null>(null);
const savingKey = ref('');
const reviewError = ref('');
let requestId = 0;

const activeItems = computed(() => active.value?.items ?? []);
const activeLabels = computed(() => active.value ? observationMetricLabels(active.value) : ['Observed value', 'Compared with', 'Result']);
const isGrouped = computed(() => activeItems.value.length > 1);
const uniqueEntities = computed(() => new Set(activeItems.value.map((item) => item.entityLabel ?? item.label)).size);

async function load(preserveUndo = false): Promise<void> {
  const current = ++requestId;
  active.value = null;
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
function handleKeydown(event: KeyboardEvent): void { if (event.key === 'Escape' && active.value) close(); }
function openActivity(item: ObservationFinding): void { close(); emit('openActivity', observationActivity(item)); }

async function review(item: ObservationFinding, remove = false): Promise<void> {
  const body = observationReviewRequest(item, remove);
  if (!body) return;
  savingKey.value = item.findingKey ?? '';
  reviewError.value = '';
  try {
    await saveObservationReview(body);
    lastReview.value = remove ? null : item;
    close();
    await load(true);
  } catch (caught) {
    reviewError.value = caught instanceof Error ? caught.message : 'Could not save the observation review';
  } finally {
    savingKey.value = '';
  }
}

watch([() => props.period, () => props.month, () => props.card, () => props.incomeHidden, () => props.refreshKey], () => { void load(); }, { immediate: true });
onMounted(() => document.addEventListener('keydown', handleKeydown));
onBeforeUnmount(() => document.removeEventListener('keydown', handleKeydown));
</script>

<template>
  <article class="observations-panel-preview" :class="{ compact: response && !response.findingCount }" aria-labelledby="observations-preview-title" :aria-busy="loading">
    <header class="observations-head-preview">
      <div><h2 id="observations-preview-title">{{ response?.historical ? 'Financial patterns' : 'Financial observations' }}</h2><p v-if="response">{{ observationScope(response) }}</p><p v-else>Checking the selected period against your local history…</p></div>
      <strong v-if="response">{{ observationCount(response) }}</strong>
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
    <div v-else-if="response" class="observations-empty-preview">{{ response.historical ? 'No sustained shift was strong enough to describe as a new normal.' : 'No financial observation crossed its threshold.' }}</div>
    <div v-else class="observations-state-preview">Analyzing local financial activity…</div>
    <span v-if="loading && response" class="observations-updating-preview">Updating…</span>
  </article>

  <Teleport to="body"><div v-if="active" class="observation-modal-backdrop-preview" @mousedown.self="close"><section class="observation-modal-preview" role="dialog" aria-modal="true" aria-labelledby="observation-preview-modal-title">
    <button type="button" class="observation-modal-close-preview" aria-label="Close observation details" @click="close">×</button>
    <header :style="{ '--observation-color': observationVisual(active.type).color }"><span><i>{{ observationVisual(active.type).icon }}</i>{{ active.type }}</span><h2 id="observation-preview-modal-title">{{ active.title }}</h2><p>{{ active.description }}</p></header>
    <div class="observation-modal-body-preview">
      <div class="observation-metrics-preview">
        <div><span>{{ isGrouped ? 'Findings' : activeLabels[0] }}</span><strong>{{ isGrouped ? activeItems.length : active.value }}</strong></div>
        <div><span>{{ isGrouped ? (active.entities ?? 'Merchants') : activeLabels[1] }}</span><strong>{{ isGrouped ? uniqueEntities : (active.comparison ?? 'Selected-period history') }}</strong></div>
        <div><span>{{ isGrouped ? 'Period' : activeLabels[2] }}</span><strong>{{ isGrouped ? `${response?.observedStart} – ${response?.observedEnd}` : (active.result ?? 'Review') }}</strong></div>
      </div>
      <section v-if="active.ruleText" class="observation-rule-preview"><strong>Why this appeared</strong><p>{{ active.ruleText }}</p></section>
      <section class="observation-findings-preview"><div><h3>{{ isGrouped ? 'Related findings' : 'Calculation & source evidence' }}</h3><span v-if="isGrouped">{{ activeItems.length }} findings</span></div>
        <details v-for="item in activeItems" :key="`${item.type}:${item.findingKey ?? item.month}:${item.label}`" :open="!isGrouped">
          <summary><span><strong dir="auto">{{ evidenceLabel(item) }}</strong><small>{{ item.entitySublabel ?? item.month }}</small></span><b>{{ item.value }}</b><b>{{ item.comparison ?? 'Selected-period history' }}</b><b>{{ item.result ?? 'Review' }}</b></summary>
          <div><p v-if="item.eventLabel" class="observation-event-preview">Event · {{ item.eventLabel }}</p><p v-if="item.comparisonDetail"><span>Comparison method</span>{{ item.comparisonDetail }}</p><ul><li v-for="(evidence,index) in item.evidence" :key="index"><span>Source {{ index + 1 }}</span><strong dir="auto">{{ evidence }}</strong></li><li v-if="!item.evidence.length"><span>Source</span><strong>No additional source rows</strong></li></ul><div class="observation-actions-preview"><button v-if="observationReviewOption(item.type) && item.findingKey" type="button" class="observation-review-button-preview" :disabled="savingKey === item.findingKey" @click="review(item)">{{ savingKey === item.findingKey ? 'Saving…' : observationReviewOption(item.type)?.action }}</button><button type="button" class="observation-activity-button-preview" @click="openActivity(item)">{{ observationActivity(item).label }}</button></div></div>
        </details>
      </section>
      <p v-if="reviewError && active" class="observation-review-error-preview">{{ reviewError }}</p>
    </div>
  </section></div></Teleport>
  <Teleport to="body"><div v-if="lastReview" class="observation-undo-preview" role="status"><span><strong>{{ observationReviewOption(lastReview.type)?.resolved }}</strong><small dir="auto">{{ lastReview.label }}</small></span><button type="button" :disabled="Boolean(savingKey)" @click="review(lastReview,true)">Undo</button><button type="button" aria-label="Dismiss review confirmation" @click="lastReview = null">×</button></div><div v-else-if="reviewError && !active" class="observation-undo-preview error" role="alert"><span><strong>Review could not be updated</strong><small>{{ reviewError }}</small></span><button type="button" aria-label="Dismiss error" @click="reviewError = ''">×</button></div></Teleport>
</template>
