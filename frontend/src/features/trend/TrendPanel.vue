<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import type { DashboardResponse } from '../../api/contracts';
import { formatCompact, formatDate, formatMoney, formatMonth } from '../../shared/format';
import { UiPanel, UiSkeleton } from '../../shared/ui';
import { axisValues, billingAxisLabel, buildBillingTrend, buildMonthlyTrend, CHART } from './model';

const props = defineProps<{
  dashboard: DashboardResponse | null;
  incomeHidden: boolean;
  loading: boolean;
}>();

const activeIndex = ref<number | null>(null);
const chartRoot = ref<HTMLElement | null>(null);
const tooltipPosition = ref({ left: '50%', top: '22px' });
const isMonth = computed(() => props.dashboard?.period.key === 'month');
const showIncome = computed(() => Boolean(props.dashboard && !props.incomeHidden && props.dashboard.selected_card === 'all' && props.dashboard.income_summary.has_income));
const monthly = computed(() => props.dashboard ? buildMonthlyTrend(props.dashboard.trend, props.dashboard.categories, props.dashboard.period) : null);
const billing = computed(() => props.dashboard ? buildBillingTrend(props.dashboard.trend, showIncome.value) : null);
const activeDaily = computed(() => !isMonth.value || activeIndex.value === null ? null : monthly.value?.days[activeIndex.value] ?? null);
const activeBilling = computed(() => isMonth.value || activeIndex.value === null ? null : billing.value?.bars[activeIndex.value] ?? null);
const activeDailyCategories = computed(() => [...(activeDaily.value?.categories ?? [])].sort((left, right) => Math.abs(Number(right.amount)) - Math.abs(Number(left.amount))));
const scopeLabel = computed(() => props.dashboard?.selected_card === 'all' ? 'all cards' : 'selected card');
const subtitle = computed(() => {
  if (!props.dashboard) return '';
  if (isMonth.value) {
    const summary = props.dashboard.purchase_activity_summary;
    return `${formatMoney(summary?.total ?? 0)} total · billed charges ${formatMoney(summary?.billed_charges ?? 0)}`;
  }
  const note = props.incomeHidden ? ' · income hidden' : props.dashboard.selected_card !== 'all' ? ' · income comparison available for all cards' : '';
  return `Monthly spending · ${scopeLabel.value}${note}`;
});

function positionTooltip(event: MouseEvent | FocusEvent): void {
  const wrap = chartRoot.value;
  const target = event.currentTarget as Element | null;
  if (!wrap || !target) return;
  const wrapRect = wrap.getBoundingClientRect();
  let clientX: number;
  let clientY: number;
  if (event instanceof MouseEvent) {
    clientX = event.clientX;
    clientY = event.clientY;
  } else {
    const targetRect = target.getBoundingClientRect();
    clientX = targetRect.left + targetRect.width / 2;
    clientY = targetRect.top + Math.min(targetRect.height / 2, 70);
  }
  tooltipPosition.value = {
    left: `${Math.min(Math.max(clientX - wrapRect.left, 75), wrapRect.width - 75)}px`,
    top: `${Math.max(clientY - wrapRect.top - 12, 22)}px`,
  };
}

function activatePoint(index: number, event: MouseEvent | FocusEvent): void {
  activeIndex.value = index;
  positionTooltip(event);
}

watch(() => props.dashboard, () => { activeIndex.value = null; });
</script>

<template>
  <UiPanel class="trend-panel" aria-labelledby="trend-panel-title" :aria-busy="loading">
    <template #header><header class="trend-head">
      <div><h2 id="trend-panel-title">{{ dashboard ? (isMonth ? 'Purchase activity' : 'Income and spending') : 'Spending trend' }}</h2><p v-if="dashboard">{{ subtitle }}</p><UiSkeleton v-else-if="loading" class="trend-heading-skeleton" shape="line" /></div>
      <div class="trend-legend">
        <template v-if="dashboard && isMonth"><span><i class="stack" />Categories by day</span><span><i class="refund" />Refunds</span><span><i class="cumulative" />Cumulative purchase value</span></template>
        <template v-else-if="dashboard"><span v-if="showIncome"><i class="income" />Income</span><span><i class="spending" />Net spending</span></template>
      </div>
    </header></template>

    <div v-if="loading && !dashboard" class="trend-skeleton" aria-hidden="true"><div class="trend-skeleton-axis"><UiSkeleton v-for="index in 5" :key="index" shape="line" /></div><div class="trend-skeleton-chart"><UiSkeleton v-for="index in 12" :key="index" class="trend-skeleton-bar" /></div></div>
    <div v-else-if="!dashboard" class="trend-empty dashboard-panel-error">Dashboard trend data is unavailable.</div>
    <div v-else-if="!dashboard.trend.length" class="trend-empty">{{ isMonth ? `No purchases made during ${dashboard.period.label}` : 'No spending data' }}</div>
    <div v-else ref="chartRoot" class="trend-chart" :class="{ 'dual-axis': isMonth }" @mouseleave="activeIndex = null">
      <div class="trend-y-axis"><span v-for="value in axisValues(isMonth ? (monthly?.dailyMax ?? 1) : (billing?.max ?? 1))" :key="value">₪{{ formatCompact(value) }}</span></div>
      <div v-if="isMonth" class="trend-y-axis right"><span v-for="value in axisValues(monthly?.cumulativeMax ?? 1)" :key="value">₪{{ formatCompact(value) }}</span></div>
      <svg :viewBox="`0 0 ${CHART.width} 235`" preserveAspectRatio="none" role="img" :aria-label="isMonth ? 'Daily purchase activity by category' : 'Monthly income and spending'">
        <defs><pattern id="preview-refund-hatch" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="4" height="4" fill="var(--ui-danger-soft)"/><rect width="2" height="4" fill="var(--ui-danger)"/></pattern></defs>
        <g class="trend-gridlines"><line v-for="y in [14,65,116,167,218]" :key="y" x1="0" :y1="y" :x2="CHART.width" :y2="y" /></g>
        <template v-if="isMonth">
          <g v-for="(day, index) in monthly?.days ?? []" :key="day.bucket">
            <rect v-for="segment in day.segments" :key="segment.category" class="trend-category-segment" :x="segment.x" :y="segment.y" :width="segment.width" :height="segment.height" :fill="segment.color" />
            <rect v-if="day.refunds" :x="day.x - (day.segments[0]?.width ?? 3) / 2" :y="CHART.bottom - 3" :width="day.segments[0]?.width ?? 3" height="3" fill="url(#preview-refund-hatch)" />
            <rect class="trend-hit" tabindex="0" role="button" :aria-label="`${formatDate(day.bucket)}, ${formatMoney(day.amount)} net purchases`" :x="index * CHART.width / (monthly?.days.length || 1)" y="14" :width="CHART.width / (monthly?.days.length || 1)" height="204" @mousemove="activatePoint(index,$event)" @click="activatePoint(index,$event)" @focus="activatePoint(index,$event)" @blur="activeIndex = null" />
          </g>
          <path class="trend-cumulative-line" :d="monthly?.path ?? ''" />
        </template>
        <template v-else>
          <g v-for="(bar, index) in billing?.bars ?? []" :key="bar.bucket">
            <rect v-if="billing?.showIncome" class="trend-income-bar" :x="bar.incomeX" :y="bar.incomeY" :width="bar.width" :height="bar.incomeHeight" rx="3" />
            <rect class="trend-spending-bar" :x="bar.spendingX" :y="bar.spendingY" :width="bar.width" :height="bar.spendingHeight" rx="3" />
            <rect class="trend-hit" tabindex="0" role="button" :aria-label="`${formatMonth(bar.bucket)}, ${formatMoney(bar.amount)} net spending`" :x="bar.hitX" y="14" :width="bar.hitWidth" height="204" @mousemove="activatePoint(index,$event)" @click="activatePoint(index,$event)" @focus="activatePoint(index,$event)" @blur="activeIndex = null" />
          </g>
        </template>
      </svg>
      <div class="trend-x-axis">
        <span v-for="item in (isMonth ? (monthly?.labels ?? []) : (billing?.labels ?? []))" :key="`${item.x}-${item.label}`" :style="{ left: `${item.x}%` }">{{ isMonth ? item.label : billingAxisLabel(item.label,billing?.bars.length ?? 0) }}</span>
      </div>
      <div v-if="activeDaily" class="trend-tooltip" :style="tooltipPosition">
        <strong>{{ formatDate(activeDaily.bucket) }} · {{ formatMoney(activeDaily.amount) }} net</strong>
        <span v-for="item in activeDailyCategories" :key="item.category"><b>{{ item.category }}</b>{{ formatMoney(item.amount) }}</span>
        <small v-if="activeDaily.refunds">Gross {{ formatMoney(activeDaily.gross) }} · refunds {{ formatMoney(-activeDaily.refunds) }}</small>
        <small>Cumulative {{ formatMoney(activeDaily.cumulative) }}</small>
      </div>
      <div v-else-if="activeBilling" class="trend-tooltip" :style="tooltipPosition">
        <strong>{{ formatMonth(activeBilling.bucket) }}</strong>
        <span><b>Net spending</b>{{ formatMoney(activeBilling.amount) }}</span>
        <span v-if="billing?.showIncome"><b>Income</b>{{ formatMoney(activeBilling.income) }}</span>
        <small v-if="billing?.showIncome">Amount left {{ formatMoney(activeBilling.income - activeBilling.amount) }}</small>
      </div>
    </div>
  </UiPanel>
</template>
