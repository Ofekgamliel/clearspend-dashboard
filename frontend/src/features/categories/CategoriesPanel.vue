<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { getCategories } from '../../api/categories';
import type { CategoriesResponse, CategoryRow, EventScope, PeriodKey } from '../../api/contracts';
import { formatInteger, formatMoney, formatMonth, formatPercent } from '../../shared/format';
import { UiDialog } from '../../shared/ui';
import { buildCategorySegments, categoryComparisonModel, categorySegmentAtPoint, type CategorySegment } from './model';

const scope = ref<EventScope>('all');
const props = defineProps<{
  period: PeriodKey;
  month: string;
  card: string;
  refreshKey: number;
}>();
const emit = defineEmits<{
  openCategory: [payload: { category: string; routine: boolean }];
}>();
const response = ref<CategoriesResponse | null>(null);
const loading = ref(true);
const error = ref('');
const overviewOpen = ref(false);
const activeDonutSegment = ref<CategorySegment | null>(null);
const donutTooltipPosition = ref({ left: '50%', top: '50%' });
let requestId = 0;

const donut = computed(() => buildCategorySegments(response.value?.categories ?? []));

async function loadCategories(): Promise<void> {
  const currentRequest = ++requestId;
  loading.value = true;
  error.value = '';
  try {
    const payload = await getCategories({
      period: props.period,
      month: props.month,
      card: props.card,
      eventScope: scope.value,
    });
    if (currentRequest === requestId) response.value = payload;
  } catch (caught) {
    if (currentRequest !== requestId) return;
    error.value = caught instanceof Error ? caught.message : 'Could not load categories';
  } finally {
    if (currentRequest === requestId) loading.value = false;
  }
}

function comparisonFor(category: CategoryRow) {
  if (!response.value) return null;
  return categoryComparisonModel(category, response.value.category_comparison);
}

function comparisonTitle(category: CategoryRow): string {
  const comparison = comparisonFor(category);
  if (!comparison) return 'Previous-month comparison is unavailable';
  const previousMonth = formatMonth(comparison.previousMonth);
  if (comparison.status === 'new') return `No spending in ${previousMonth}`;
  if (comparison.status === 'unavailable') return `Comparison with ${previousMonth} is unavailable`;
  return `${formatMoney(category.previous_amount ?? 0)} in ${previousMonth}`;
}

function openOverview(): void {
  overviewOpen.value = true;
}

function closeOverview(): void {
  overviewOpen.value = false;
}

function chooseCategory(category: string): void {
  closeOverview();
  emit('openCategory', { category, routine: scope.value === 'routine' });
}

function showDonutSegment(segment: CategorySegment, left = '50%', top = '50%'): void {
  activeDonutSegment.value = segment;
  donutTooltipPosition.value = { left, top };
}

function handleDonutPointer(event: MouseEvent): void {
  const element = event.currentTarget as HTMLElement;
  const rect = element.getBoundingClientRect();
  const segment = categorySegmentAtPoint(event.clientX - rect.left, event.clientY - rect.top, rect.width, donut.value.segments);
  if (!segment) {
    activeDonutSegment.value = null;
    return;
  }
  showDonutSegment(segment, `${event.clientX - rect.left}px`, `${event.clientY - rect.top}px`);
}

function focusDonut(): void {
  if (!activeDonutSegment.value && donut.value.segments[0]) showDonutSegment(donut.value.segments[0]);
}

function handleDonutKeydown(event: KeyboardEvent): void {
  if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End'].includes(event.key)) return;
  event.preventDefault();
  const segments = donut.value.segments;
  if (!segments.length) return;
  const current = Math.max(0, segments.findIndex((segment) => segment.category === activeDonutSegment.value?.category));
  let next = current;
  if (event.key === 'Home') next = 0;
  else if (event.key === 'End') next = segments.length - 1;
  else if (event.key === 'ArrowRight' || event.key === 'ArrowDown') next = (current + 1) % segments.length;
  else next = (current - 1 + segments.length) % segments.length;
  showDonutSegment(segments[next]);
}

watch(
  [scope, () => props.period, () => props.month, () => props.card, () => props.refreshKey],
  loadCategories,
  { immediate: true },
);
</script>

<template>
  <article class="categories-panel" aria-labelledby="categories-title">
    <header class="categories-head">
      <div>
        <h2 id="categories-title">Categories</h2>
      </div>
      <div class="category-head-actions">
        <div class="scope-toggle" role="group" aria-label="Category spending scope">
          <button type="button" :class="{ active: scope === 'all' }" :aria-pressed="scope === 'all'" @click="scope = 'all'">All spending</button>
          <button type="button" :class="{ active: scope === 'routine' }" :aria-pressed="scope === 'routine'" @click="scope = 'routine'">Routine only</button>
        </div>
        <button type="button" class="category-view-details" :disabled="!response?.categories.length" @click="openOverview">View details →</button>
      </div>
    </header>

    <div v-if="loading && !response" class="panel-state" role="status">Loading categories…</div>
    <div v-else-if="error" class="panel-state error-state" role="alert">
      <span>{{ error }}</span>
      <button type="button" @click="loadCategories">Try again</button>
    </div>
    <div v-else-if="!response?.categories.length" class="panel-state">No category spending is available for this period.</div>
    <div v-else class="categories-body" :aria-busy="loading">
      <div class="category-donut" role="img" tabindex="0" :aria-label="`${donut.ariaLabel}. Use arrow keys to inspect categories.`" :style="{ background: donut.gradient }" @mousemove="handleDonutPointer" @mouseleave="activeDonutSegment = null" @focus="focusDonut" @blur="activeDonutSegment = null" @keydown="handleDonutKeydown">
        <div class="donut-centre"><strong>{{ formatMoney(response.total) }}</strong><span>Total</span></div>
        <span v-if="activeDonutSegment" class="category-donut-tooltip" role="tooltip" :style="donutTooltipPosition"><strong>{{ activeDonutSegment.category }}</strong><span>{{ formatMoney(activeDonutSegment.amount) }} · {{ formatPercent(activeDonutSegment.share) }}</span></span>
      </div>

      <div class="category-list" aria-label="Category spending breakdown">
        <div class="category-columns" aria-hidden="true"><span /><span>Category</span><span>Amount</span><span>Share</span><span>Vs prior</span></div>
        <button v-for="segment in donut.segments" :key="segment.category" type="button" class="category-row" :aria-label="`View transactions in ${segment.category}`" @click="emit('openCategory', { category: segment.category, routine: scope === 'routine' })">
          <i class="category-dot" :style="{ background: segment.color }" />
          <span class="category-name" dir="auto">{{ segment.category }}</span>
          <strong>{{ formatMoney(segment.amount) }}</strong>
          <span class="category-share">{{ formatPercent(segment.share) }}</span>
          <span v-if="comparisonFor(segment)" class="comparison-badge" :class="comparisonFor(segment)?.status" :title="comparisonTitle(segment)">{{ comparisonFor(segment)?.label }}</span>
          <span v-else class="comparison-badge unavailable">—</span>
        </button>
      </div>
      <div v-if="loading" class="refresh-indicator" role="status">Updating…</div>
    </div>
  </article>

  <UiDialog :open="overviewOpen && Boolean(response)" title-id="category-overview-title" close-label="Close category overview" size="standard" @request-close="closeOverview">
    <template v-if="response" #header><div class="category-overview-head"><h2 id="category-overview-title">All categories</h2></div></template>
    <template v-if="response">
        <div class="category-overview-summary"><strong>{{ response.categories.length }} categories</strong><span>Select a category to view its transactions</span><b>{{ formatMoney(response.total) }} total</b></div>
        <div class="category-overview-list">
          <button v-for="(item,index) in response.categories" :key="item.category" type="button" @click="chooseCategory(item.category)">
            <i :style="{ background: donut.segments[index]?.color }" />
            <span><strong dir="auto">{{ item.category }}</strong><small>{{ formatInteger(item.transactions) }} transactions · {{ formatInteger(item.merchants) }} merchants</small><b><em :style="{ width: `${Math.min(item.share,100)}%` }" /></b></span>
            <span><strong>{{ formatMoney(item.amount) }}</strong><small>{{ formatPercent(item.share) }} · View transactions →</small></span>
          </button>
        </div>
    </template>
  </UiDialog>
</template>
