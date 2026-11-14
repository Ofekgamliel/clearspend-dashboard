<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import type { DashboardCard, PeriodKey } from '../../api/contracts';
import { formatMonth } from '../../shared/format';
import { availableMonthYears, cardLabel, normalizeAvailableMonths } from './model';

const props = defineProps<{
  period: PeriodKey;
  month: string;
  card: string;
  cards: DashboardCard[];
  availableMonths: string[];
  loading: boolean;
  error: string;
}>();

const emit = defineEmits<{
  periodChange: [period: PeriodKey];
  monthChange: [month: string];
  cardChange: [card: string];
  retry: [];
}>();

const monthRoot = ref<HTMLElement | null>(null);
const cardRoot = ref<HTMLElement | null>(null);
const monthButton = ref<HTMLButtonElement | null>(null);
const cardButton = ref<HTMLButtonElement | null>(null);
const monthOpen = ref(false);
const cardOpen = ref(false);
const viewYear = ref(0);

const normalizedMonths = computed(() => normalizeAvailableMonths(props.availableMonths));
const availableSet = computed(() => new Set(normalizedMonths.value));
const years = computed(() => availableMonthYears(props.availableMonths));
const selectedCard = computed(() => props.cards.find((item) => item.key === props.card));
const monthLabels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const yearIndex = computed(() => years.value.indexOf(viewYear.value));

function selectedYear(): number {
  const candidate = Number((props.month || normalizedMonths.value[0] || '').slice(0, 4));
  return years.value.includes(candidate) ? candidate : (years.value.at(-1) ?? new Date().getFullYear());
}

function closeMonth(restoreFocus = false): void {
  monthOpen.value = false;
  if (restoreFocus) void nextTick(() => monthButton.value?.focus());
}

function closeCard(restoreFocus = false): void {
  cardOpen.value = false;
  if (restoreFocus) void nextTick(() => cardButton.value?.focus());
}

function toggleMonth(): void {
  const open = !monthOpen.value;
  closeCard();
  viewYear.value = selectedYear();
  monthOpen.value = open;
}

function toggleCard(): void {
  const open = !cardOpen.value;
  closeMonth();
  cardOpen.value = open;
}

function monthValue(index: number): string {
  return `${viewYear.value}-${String(index + 1).padStart(2, '0')}`;
}

function chooseMonth(value: string): void {
  if (!availableSet.value.has(value)) return;
  closeMonth();
  emit('monthChange', value);
}

function chooseLatest(): void {
  const latest = normalizedMonths.value[0];
  if (latest) chooseMonth(latest);
}

function chooseCard(value: string): void {
  closeCard();
  emit('cardChange', value);
}

function previousYear(): void {
  if (yearIndex.value > 0) viewYear.value = years.value[yearIndex.value - 1];
}

function nextYear(): void {
  if (yearIndex.value >= 0 && yearIndex.value < years.value.length - 1) viewYear.value = years.value[yearIndex.value + 1];
}

function handlePointerDown(event: PointerEvent): void {
  const target = event.target as Node;
  if (monthOpen.value && !monthRoot.value?.contains(target)) closeMonth();
  if (cardOpen.value && !cardRoot.value?.contains(target)) closeCard();
}

function handleKeydown(event: KeyboardEvent): void {
  if (event.key !== 'Escape') return;
  if (monthOpen.value) closeMonth(true);
  else if (cardOpen.value) closeCard(true);
}

watch([() => props.month, normalizedMonths], () => { if (!monthOpen.value) viewYear.value = selectedYear(); }, { immediate: true });
onMounted(() => { document.addEventListener('pointerdown', handlePointerDown); document.addEventListener('keydown', handleKeydown); });
onBeforeUnmount(() => { document.removeEventListener('pointerdown', handlePointerDown); document.removeEventListener('keydown', handleKeydown); });
</script>

<template>
  <section class="dashboard-filters" aria-label="Dashboard filters" :aria-busy="loading">
    <div class="period-tabs" role="group" aria-label="Reporting period">
      <button type="button" :class="{ active: period === 'month' }" :aria-pressed="period === 'month'" @click="emit('periodChange', 'month')">Month</button>
      <button type="button" :class="{ active: period === 'year' }" :aria-pressed="period === 'year'" @click="emit('periodChange', 'year')">Latest year</button>
      <button type="button" :class="{ active: period === 'all' }" :aria-pressed="period === 'all'" @click="emit('periodChange', 'all')">All time</button>
    </div>

    <div ref="monthRoot" class="month-picker">
      <button ref="monthButton" type="button" class="month-picker-button" aria-label="Choose month" aria-haspopup="dialog" :aria-expanded="monthOpen" :disabled="!normalizedMonths.length" @click="toggleMonth">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 2h2v2h6V2h2v2h2a2 2 0 0 1 2 2v14H3V6a2 2 0 0 1 2-2h2V2ZM5 9v9h14V9H5Z"/></svg>
        <strong>{{ month ? formatMonth(month) : 'No months available' }}</strong><b aria-hidden="true">⌄</b>
      </button>
      <div v-if="monthOpen" class="month-picker-popover" role="dialog" aria-label="Choose a reporting month">
        <div class="month-picker-year"><button type="button" aria-label="Previous available year" :disabled="yearIndex <= 0" @click="previousYear">‹</button><strong>{{ viewYear }}</strong><button type="button" aria-label="Next available year" :disabled="yearIndex < 0 || yearIndex >= years.length - 1" @click="nextYear">›</button></div>
        <div class="month-picker-grid"><button v-for="(label,index) in monthLabels" :key="label" type="button" class="month-picker-month" :class="{ available: availableSet.has(monthValue(index)), selected: month === monthValue(index) }" :disabled="!availableSet.has(monthValue(index))" :aria-label="formatMonth(monthValue(index))" :aria-current="month === monthValue(index) ? 'date' : undefined" @click="chooseMonth(monthValue(index))">{{ label }}</button></div>
        <div class="month-picker-footer"><span><i aria-hidden="true" /> Imported data</span><button type="button" @click="chooseLatest">Latest month</button></div>
      </div>
    </div>

    <div ref="cardRoot" class="card-picker">
      <button ref="cardButton" type="button" class="card-picker-button" aria-label="Choose card" aria-haspopup="listbox" :aria-expanded="cardOpen" @click="toggleCard"><span>Card</span><strong>{{ cardLabel(selectedCard) }}</strong><b aria-hidden="true">⌄</b></button>
      <div v-if="cardOpen" class="card-picker-popover" role="listbox" aria-label="Choose a card">
        <button type="button" class="card-picker-option" :class="{ selected: card === 'all' }" role="option" :aria-selected="card === 'all'" @click="chooseCard('all')"><span><strong>All cards</strong><small>Combined dashboard view</small></span><i>{{ card === 'all' ? '✓' : '' }}</i></button>
        <button v-for="item in cards" :key="item.key" type="button" class="card-picker-option" :class="{ selected: card === item.key }" role="option" :aria-selected="card === item.key" @click="chooseCard(item.key)"><span><strong>{{ cardLabel(item) }}</strong><small>{{ item.provider.toUpperCase() }}</small></span><i>{{ card === item.key ? '✓' : '' }}</i></button>
      </div>
    </div>

    <div v-if="error" class="filter-error" role="alert"><span>{{ error }}</span><button type="button" @click="emit('retry')">Retry</button></div>
    <span v-else-if="loading" class="filter-loading" role="status">Updating…</span>
  </section>
</template>
