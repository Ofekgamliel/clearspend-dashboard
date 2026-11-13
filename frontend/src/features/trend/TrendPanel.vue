<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import type { DashboardResponse } from '../../api/contracts';
import { formatCompact, formatDate, formatMoney, formatShortMonth } from '../../shared/format';
import { axisValues, buildBillingTrend, buildMonthlyTrend, CHART } from './model';

const props = defineProps<{
  dashboard: DashboardResponse;
  incomeHidden: boolean;
  loading: boolean;
}>();

const activeIndex = ref<number | null>(null);
const isMonth = computed(() => props.dashboard.period.key === 'month');
const showIncome = computed(() => !props.incomeHidden && props.dashboard.selected_card === 'all' && props.dashboard.income_summary.has_income);
const monthly = computed(() => buildMonthlyTrend(props.dashboard.trend, props.dashboard.categories, props.dashboard.period));
const billing = computed(() => buildBillingTrend(props.dashboard.trend, showIncome.value));
const activeDaily = computed(() => activeIndex.value === null ? null : monthly.value.days[activeIndex.value] ?? null);
const activeBilling = computed(() => activeIndex.value === null ? null : billing.value.bars[activeIndex.value] ?? null);
const scopeLabel = computed(() => props.dashboard.selected_card === 'all' ? 'all cards' : 'selected card');
const subtitle = computed(() => {
  if (isMonth.value) {
    const summary = props.dashboard.purchase_activity_summary;
    return `Purchases made during ${props.dashboard.period.label} · installments counted once · ${scopeLabel.value} · ${formatMoney(summary?.total ?? 0)} total · billed charges ${formatMoney(summary?.billed_charges ?? 0)}`;
  }
  const note = props.incomeHidden ? ' · income hidden' : props.dashboard.selected_card !== 'all' ? ' · income comparison available for all cards' : '';
  return `Monthly spending · ${scopeLabel.value}${note}`;
});

watch(() => props.dashboard, () => { activeIndex.value = null; });
</script>

<template>
  <article class="trend-panel" :aria-busy="loading">
    <header class="trend-head">
      <div><h2>{{ isMonth ? 'Purchase activity' : 'Income and spending' }}</h2><p>{{ subtitle }}</p></div>
      <div class="trend-legend">
        <template v-if="isMonth"><span><i class="stack" />Categories by day</span><span><i class="refund" />Refunds</span><span><i class="cumulative" />Cumulative purchase value</span></template>
        <template v-else><span v-if="showIncome"><i class="income" />Income</span><span><i class="spending" />Net spending</span></template>
      </div>
    </header>

    <div v-if="!dashboard.trend.length" class="trend-empty">{{ isMonth ? `No purchases made during ${dashboard.period.label}` : 'No spending data' }}</div>
    <div v-else class="trend-chart" :class="{ 'dual-axis': isMonth }" @mouseleave="activeIndex = null">
      <div class="trend-y-axis"><span v-for="value in axisValues(isMonth ? monthly.dailyMax : billing.max)" :key="value">₪{{ formatCompact(value) }}</span></div>
      <div v-if="isMonth" class="trend-y-axis right"><span v-for="value in axisValues(monthly.cumulativeMax)" :key="value">₪{{ formatCompact(value) }}</span></div>
      <svg :viewBox="`0 0 ${CHART.width} 235`" preserveAspectRatio="none" role="img" :aria-label="isMonth ? 'Daily purchase activity by category' : 'Monthly income and spending'">
        <defs><pattern id="preview-refund-hatch" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="4" height="4" fill="#f2a0a8"/><rect width="2" height="4" fill="#db5c69"/></pattern></defs>
        <g class="trend-gridlines"><line v-for="y in [14,65,116,167,218]" :key="y" x1="0" :y1="y" :x2="CHART.width" :y2="y" /></g>
        <template v-if="isMonth">
          <g v-for="(day, index) in monthly.days" :key="day.bucket">
            <rect v-for="segment in day.segments" :key="segment.category" class="trend-category-segment" :x="segment.x" :y="segment.y" :width="segment.width" :height="segment.height" :fill="segment.color" />
            <rect v-if="day.refunds" :x="day.x - (day.segments[0]?.width ?? 3) / 2" :y="CHART.bottom - 3" :width="day.segments[0]?.width ?? 3" height="3" fill="url(#preview-refund-hatch)" />
            <rect class="trend-hit" :x="index * CHART.width / monthly.days.length" y="14" :width="CHART.width / monthly.days.length" height="204" @mouseenter="activeIndex = index" @focus="activeIndex = index" />
          </g>
          <path class="trend-cumulative-line" :d="monthly.path" />
        </template>
        <template v-else>
          <g v-for="(bar, index) in billing.bars" :key="bar.bucket">
            <rect v-if="billing.showIncome" class="trend-income-bar" :x="bar.incomeX" :y="bar.incomeY" :width="bar.width" :height="bar.incomeHeight" rx="3" />
            <rect class="trend-spending-bar" :x="bar.spendingX" :y="bar.spendingY" :width="bar.width" :height="bar.spendingHeight" rx="3" />
            <rect class="trend-hit" :x="bar.hitX" y="14" :width="bar.hitWidth" height="204" @mouseenter="activeIndex = index" @focus="activeIndex = index" />
          </g>
        </template>
      </svg>
      <div class="trend-x-axis">
        <span v-for="item in (isMonth ? monthly.labels : billing.labels)" :key="`${item.x}-${item.label}`" :style="{ left: `${item.x}%` }">{{ isMonth ? item.label : formatShortMonth(item.label) }}</span>
      </div>
      <div v-if="activeDaily" class="trend-tooltip">
        <strong>{{ formatDate(activeDaily.bucket) }} · {{ formatMoney(activeDaily.amount) }} net</strong>
        <span v-for="item in activeDaily.categories" :key="item.category"><b>{{ item.category }}</b>{{ formatMoney(item.amount) }}</span>
        <small v-if="activeDaily.refunds">Gross {{ formatMoney(activeDaily.gross) }} · refunds {{ formatMoney(-activeDaily.refunds) }}</small>
        <small>Cumulative {{ formatMoney(activeDaily.cumulative) }}</small>
      </div>
      <div v-else-if="activeBilling" class="trend-tooltip">
        <strong>{{ formatShortMonth(activeBilling.bucket) }}</strong>
        <span><b>Net spending</b>{{ formatMoney(activeBilling.amount) }}</span>
        <span v-if="billing.showIncome"><b>Income</b>{{ formatMoney(activeBilling.income) }}</span>
        <small v-if="billing.showIncome">Amount left {{ formatMoney(activeBilling.income - activeBilling.amount) }}</small>
      </div>
    </div>
  </article>
</template>
