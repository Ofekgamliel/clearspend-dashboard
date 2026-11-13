<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { getEvents } from '../../api/events';
import type { EventSummary, EventsResponse, EventTransaction, PeriodKey } from '../../api/contracts';
import { formatDate, formatMoney } from '../../shared/format';
import { buildEventPanelItems, categoryTotals, eventIcon, isBusinessTrip, type EventGroupItem } from './model';

const colors = ['#6658e8', '#41b98c', '#e6a14b', '#5b8def', '#d76a8a', '#7f74c9', '#3aa6a0', '#d17c43'];
const props = defineProps<{ period: PeriodKey; month: string; card: string }>();
const response = ref<EventsResponse | null>(null);
const loading = ref(true);
const error = ref('');
const modalOpen = ref(false);
const activeEvent = ref<EventSummary | null>(null);
const activeGroup = ref<EventGroupItem | null>(null);
const showGroup = ref(false);
const activeCategory = ref('all');
let requestId = 0;

const items = computed(() => buildEventPanelItems(response.value?.events ?? [], props.period));
const combinedSpending = computed(() => (response.value?.events ?? []).reduce((sum, event) => sum + Number(event.amount || 0), 0));
const categories = computed(() => categoryTotals(activeEvent.value?.transactions ?? []));
const visibleTransactions = computed<EventTransaction[]>(() => {
  const rows = activeEvent.value?.transactions ?? [];
  return activeCategory.value === 'all' ? rows : rows.filter((item) => item.category === activeCategory.value);
});
const groupTransactions = computed(() => activeGroup.value?.events.flatMap((event) => event.transactions) ?? []);
const groupCategories = computed(() => new Set(groupTransactions.value.map((item) => item.category)).size);
const groupCards = computed(() => new Set(groupTransactions.value.map((item) => `${item.provider}:${item.card_last4}`)).size);

async function loadEvents(): Promise<void> {
  const current = ++requestId;
  loading.value = true;
  error.value = '';
  try {
    const payload = await getEvents({ period: props.period, month: props.month, card: props.card });
    if (current === requestId) response.value = payload;
  } catch (caught) {
    if (current === requestId) error.value = caught instanceof Error ? caught.message : 'Could not load projects and events';
  } finally {
    if (current === requestId) loading.value = false;
  }
}

function openEvent(event: EventSummary, fromGroup = false): void {
  activeEvent.value = event;
  activeCategory.value = 'all';
  showGroup.value = false;
  if (!fromGroup) activeGroup.value = null;
  modalOpen.value = true;
}

function openGroup(group: EventGroupItem): void {
  activeGroup.value = group;
  activeEvent.value = null;
  showGroup.value = true;
  modalOpen.value = true;
}

function closeModal(): void {
  modalOpen.value = false;
  activeEvent.value = null;
  activeGroup.value = null;
  showGroup.value = false;
}

function handleKeydown(event: KeyboardEvent): void { if (event.key === 'Escape' && modalOpen.value) closeModal(); }
watch([() => props.period, () => props.month, () => props.card], loadEvents, { immediate: true });
watch([() => props.period, () => props.month, () => props.card], closeModal);
onMounted(() => document.addEventListener('keydown', handleKeydown));
onBeforeUnmount(() => document.removeEventListener('keydown', handleKeydown));
</script>

<template>
  <article class="events-panel-preview" :class="{ empty: response && !response.events.length }" aria-labelledby="events-title" :aria-busy="loading">
    <header class="events-panel-head"><div class="events-title-line"><h2 id="events-title">Projects &amp; events</h2><span v-if="response && !response.events.length">No active projects</span></div><p v-if="response?.events.length">{{ response.events.length }} events · {{ formatMoney(combinedSpending) }}</p></header>
    <div v-if="error && !response" class="events-state error-state"><span>{{ error }}</span><button type="button" @click="loadEvents">Try again</button></div>
    <div v-else-if="items.length" class="events-grid-preview">
      <button v-for="item in items" :key="item.kind === 'group' ? item.id : item.event.id" type="button" class="event-card-preview" :class="{ business: item.kind === 'group' || isBusinessTrip(item.event.event_type) }" @click="item.kind === 'group' ? openGroup(item) : openEvent(item.event)">
        <span class="event-card-icon-preview"><svg v-if="item.kind === 'group' || eventIcon(item.event) === 'briefcase'" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 7V5.8A1.8 1.8 0 0 1 10.8 4h2.4A1.8 1.8 0 0 1 15 5.8V7"/><rect x="3" y="7" width="18" height="13" rx="2"/><path d="M3 12.5c4.8 2 13.2 2 18 0"/><path d="M10 13h4"/></svg><template v-else>{{ eventIcon(item.event) }}</template><i v-if="item.kind === 'group' ? item.events.every(event => event.status === 'completed') : item.event.status === 'completed'">✓</i></span>
        <span class="event-card-copy-preview"><strong>{{ item.kind === 'group' ? `נסיעות עבודה ל${item.destination}` : item.event.name }}</strong><small v-if="item.kind === 'group'">{{ item.events.length }} business trips · {{ period === 'year' ? 'Latest year' : 'All time' }}</small><small v-else>{{ formatDate(item.event.start_date) }} – {{ formatDate(item.event.end_date) }}</small></span>
        <span class="event-card-amount-preview"><strong>{{ formatMoney(item.kind === 'group' ? item.events.reduce((sum,event) => sum + Number(event.amount || 0),0) : item.event.amount) }}</strong><small>{{ period === 'month' ? 'THIS MONTH' : 'PERSONAL SPENDING' }}</small></span>
      </button>
    </div>
    <div v-else-if="!response" class="events-state">Loading projects and events…</div>
  </article>

  <Teleport to="body"><div v-if="modalOpen" class="event-modal-backdrop-preview" @mousedown.self="closeModal"><section class="event-modal-preview" role="dialog" aria-modal="true" aria-labelledby="event-modal-title"><button type="button" class="event-modal-close-preview" aria-label="Close event" @click="closeModal">×</button>
    <header class="event-modal-head-preview"><button v-if="activeGroup && !showGroup" type="button" class="event-group-back-preview" aria-label="Back to grouped business trips" @click="showGroup = true; activeEvent = null"><svg viewBox="0 0 24 24"><path d="M19 12H5"/><path d="m11 18-6-6 6-6"/></svg></button><h2 id="event-modal-title">{{ showGroup && activeGroup ? `נסיעות עבודה ל${activeGroup.destination}` : activeEvent?.name }}</h2><p v-if="showGroup && activeGroup">{{ activeGroup.events.length }} business trips · {{ period === 'year' ? 'Latest year' : 'All imported history' }}</p><p v-else-if="activeEvent">{{ isBusinessTrip(activeEvent.event_type) ? 'Business trip · ' : '' }}{{ formatDate(activeEvent.start_date) }} – {{ formatDate(activeEvent.end_date) }}</p></header>
    <div class="event-modal-body-preview">
      <template v-if="showGroup && activeGroup"><div class="event-summary-preview"><div><span>Personal spending</span><strong>{{ formatMoney(activeGroup.events.reduce((sum,event) => sum + Number(event.total_amount || 0),0)) }}</strong><small>Across these trips</small></div><div><span>Transactions</span><strong>{{ groupTransactions.length }}</strong><small>Exact transaction IDs</small></div><div><span>Categories</span><strong>{{ groupCategories }}</strong><small>Cross-category events</small></div><div><span>Cards</span><strong>{{ groupCards }}</strong><small>Across these trips</small></div></div><div class="business-trip-table-preview"><div class="business-trip-head-preview"><span>Trip</span><span>Dates</span><span>Transactions</span><span>Personal spending</span><span /></div><button v-for="event in activeGroup.events" :key="event.id" type="button" @click="openEvent(event,true)"><span><strong>{{ event.name }}</strong><small>Business trip</small></span><span>{{ formatDate(event.start_date) }} – {{ formatDate(event.end_date) }}</span><span>{{ event.total_transaction_count }}</span><b>{{ formatMoney(event.total_amount) }}</b><i>›</i></button></div></template>
      <template v-else-if="activeEvent"><div class="event-summary-preview"><div><span>Personal spending</span><strong>{{ formatMoney(activeEvent.total_amount) }}</strong><small>Entire event</small></div><div><span>Transactions</span><strong>{{ activeEvent.total_transaction_count }}</strong><small>Exact transaction membership</small></div><div><span>Categories</span><strong>{{ activeEvent.category_count }}</strong><small>Across this event</small></div><div><span>Cards</span><strong>{{ activeEvent.card_count }}</strong><small>Used during this event</small></div></div><div class="event-detail-columns-preview"><section><h3>Spending by category</h3><div class="event-category-list-preview"><button type="button" :class="{ active: activeCategory === 'all' }" @click="activeCategory = 'all'"><i style="background:#aaa8b7"/><span>All categories</span><b>{{ formatMoney(activeEvent.total_amount) }}</b></button><button v-for="(category,index) in categories" :key="category.category" type="button" :class="{ active: activeCategory === category.category }" @click="activeCategory = category.category"><i :style="{ background: colors[index % colors.length] }"/><span>{{ category.category }}</span><b>{{ formatMoney(category.amount) }}</b></button></div></section><section><h3>{{ activeCategory === 'all' ? `All transactions · ${visibleTransactions.length}` : `${activeCategory} · ${visibleTransactions.length}` }}</h3><div class="event-transaction-list-preview"><div v-for="item in visibleTransactions" :key="item.id"><span><strong>{{ item.merchant_display_name || item.merchant_raw }}</strong><small>{{ item.category }}</small></span><span>{{ formatDate(item.transaction_date) }}</span><span>{{ item.provider.toUpperCase() }} •• {{ item.card_last4 }}</span><strong>{{ formatMoney(item.personal_amount) }}</strong></div><p v-if="!visibleTransactions.length">No transactions in this category.</p></div></section></div></template>
    </div></section></div></Teleport>
</template>
