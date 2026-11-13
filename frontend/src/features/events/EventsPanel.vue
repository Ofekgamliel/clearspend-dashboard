<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import { createEvent, getEvents, saveEvent } from '../../api/events';
import type { EventSummary, EventsResponse, EventTransaction, PeriodKey } from '../../api/contracts';
import { formatDate, formatMoney } from '../../shared/format';
import { buildEventPanelItems, categoryTotals, eventFormError, eventIcon, isBusinessTrip, type EventGroupItem } from './model';

const colors = ['#6658e8', '#41b98c', '#e6a14b', '#5b8def', '#d76a8a', '#7f74c9', '#3aa6a0', '#d17c43'];
const props = defineProps<{ period: PeriodKey; month: string; card: string; refreshKey: number }>();
const response = ref<EventsResponse | null>(null);
const loading = ref(true);
const error = ref('');
const modalOpen = ref(false);
const activeEvent = ref<EventSummary | null>(null);
const activeGroup = ref<EventGroupItem | null>(null);
const showGroup = ref(false);
const activeCategory = ref('all');
const createOpen = ref(false);
const createSaving = ref(false);
const createError = ref('');
const editOpen = ref(false);
const editSaving = ref(false);
const editError = ref('');
const eventNotice = ref<{ title: string; detail: string } | null>(null);
const createForm = reactive({
  name: '', event_type: 'trip', destination: '', start_date: '', end_date: '', budget: '', status: 'planned',
});
const editForm = reactive({
  name: '', event_type: 'trip', destination: '', start_date: '', end_date: '', budget: '', status: 'planned',
});
let requestId = 0;
let noticeTimer: ReturnType<typeof setTimeout> | undefined;

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

function openCreate(): void {
  Object.assign(createForm, { name: '', event_type: 'trip', destination: '', start_date: '', end_date: '', budget: '', status: 'planned' });
  createError.value = '';
  createOpen.value = true;
}

function closeCreate(): void {
  if (createSaving.value) return;
  createOpen.value = false;
  createError.value = '';
}

function openEdit(): void {
  const event = activeEvent.value;
  if (!event) return;
  Object.assign(editForm, {
    name: event.name,
    event_type: event.event_type,
    destination: event.destination ?? '',
    start_date: event.start_date,
    end_date: event.end_date,
    budget: event.budget === null ? '' : String(event.budget),
    status: event.status,
  });
  editError.value = '';
  editOpen.value = true;
}

function closeEdit(): void {
  if (editSaving.value) return;
  editOpen.value = false;
  editError.value = '';
}

async function submitEdit(): Promise<void> {
  const event = activeEvent.value;
  if (!event) return;
  editError.value = eventFormError(editForm);
  if (editError.value) return;
  editSaving.value = true;
  try {
    const result = await saveEvent({
      event_id: event.id,
      name: editForm.name.trim(),
      event_type: editForm.event_type,
      destination: editForm.event_type === 'business_trip' ? editForm.destination.trim() : '',
      start_date: editForm.start_date,
      end_date: editForm.end_date,
      budget: editForm.budget === '' ? null : Number(editForm.budget),
      status: editForm.status as 'planned' | 'active' | 'completed' | 'cancelled',
    });
    editOpen.value = false;
    await loadEvents();
    const updated = response.value?.events.find((item) => item.id === result.event.id) ?? null;
    if (updated) activeEvent.value = updated;
    else closeModal();
    clearTimeout(noticeTimer);
    eventNotice.value = { title: 'Event updated', detail: `${result.event.name} was updated` };
    noticeTimer = setTimeout(() => { eventNotice.value = null; }, 4000);
  } catch (caught) {
    editError.value = caught instanceof Error ? caught.message : 'Could not save event';
  } finally {
    editSaving.value = false;
  }
}

async function submitCreate(): Promise<void> {
  createError.value = eventFormError(createForm);
  if (createError.value) return;
  createSaving.value = true;
  try {
    const result = await createEvent({
      name: createForm.name.trim(),
      event_type: createForm.event_type,
      destination: createForm.event_type === 'business_trip' ? createForm.destination.trim() : '',
      start_date: createForm.start_date,
      end_date: createForm.end_date,
      budget: createForm.budget === '' ? null : Number(createForm.budget),
      status: createForm.status as 'planned' | 'active' | 'completed',
    });
    createOpen.value = false;
    await loadEvents();
    clearTimeout(noticeTimer);
    eventNotice.value = { title: 'Event created', detail: `${result.event.name} is ready for transaction assignments` };
    noticeTimer = setTimeout(() => { eventNotice.value = null; }, 4000);
  } catch (caught) {
    createError.value = caught instanceof Error ? caught.message : 'Could not create event';
  } finally {
    createSaving.value = false;
  }
}

function handleKeydown(event: KeyboardEvent): void {
  if (event.key !== 'Escape') return;
  if (editOpen.value) closeEdit();
  else if (createOpen.value) closeCreate();
  else if (modalOpen.value) closeModal();
}
watch([() => props.period, () => props.month, () => props.card, () => props.refreshKey], loadEvents, { immediate: true });
watch([() => props.period, () => props.month, () => props.card], closeModal);
onMounted(() => document.addEventListener('keydown', handleKeydown));
onBeforeUnmount(() => { clearTimeout(noticeTimer); document.removeEventListener('keydown', handleKeydown); });
defineExpose({ reload: loadEvents });
</script>

<template>
  <article class="events-panel-preview" :class="{ empty: response && !response.events.length }" aria-labelledby="events-title" :aria-busy="loading">
    <header class="events-panel-head"><div><div class="events-title-line"><h2 id="events-title">Projects &amp; events</h2><span v-if="response && !response.events.length">No active projects</span></div><p v-if="response?.events.length">{{ response.events.length }} events · {{ formatMoney(combinedSpending) }}</p></div><button type="button" class="event-create-button-preview" @click="openCreate"><b>+</b> New event</button></header>
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
    <header class="event-modal-head-preview"><div><button v-if="activeGroup && !showGroup" type="button" class="event-group-back-preview" aria-label="Back to grouped business trips" @click="showGroup = true; activeEvent = null"><svg viewBox="0 0 24 24"><path d="M19 12H5"/><path d="m11 18-6-6 6-6"/></svg></button><h2 id="event-modal-title">{{ showGroup && activeGroup ? `נסיעות עבודה ל${activeGroup.destination}` : activeEvent?.name }}</h2><p v-if="showGroup && activeGroup">{{ activeGroup.events.length }} business trips · {{ period === 'year' ? 'Latest year' : 'All imported history' }}</p><p v-else-if="activeEvent">{{ isBusinessTrip(activeEvent.event_type) ? 'Business trip · ' : '' }}{{ formatDate(activeEvent.start_date) }} – {{ formatDate(activeEvent.end_date) }}</p></div><button v-if="activeEvent" type="button" class="event-edit-button-preview" @click="openEdit">Edit event</button></header>
    <div class="event-modal-body-preview">
      <template v-if="showGroup && activeGroup"><div class="event-summary-preview"><div><span>Personal spending</span><strong>{{ formatMoney(activeGroup.events.reduce((sum,event) => sum + Number(event.total_amount || 0),0)) }}</strong><small>Across these trips</small></div><div><span>Transactions</span><strong>{{ groupTransactions.length }}</strong><small>Exact transaction IDs</small></div><div><span>Categories</span><strong>{{ groupCategories }}</strong><small>Cross-category events</small></div><div><span>Cards</span><strong>{{ groupCards }}</strong><small>Across these trips</small></div></div><div class="business-trip-table-preview"><div class="business-trip-head-preview"><span>Trip</span><span>Dates</span><span>Transactions</span><span>Personal spending</span><span /></div><button v-for="event in activeGroup.events" :key="event.id" type="button" @click="openEvent(event,true)"><span><strong>{{ event.name }}</strong><small>Business trip</small></span><span>{{ formatDate(event.start_date) }} – {{ formatDate(event.end_date) }}</span><span>{{ event.total_transaction_count }}</span><b>{{ formatMoney(event.total_amount) }}</b><i>›</i></button></div></template>
      <template v-else-if="activeEvent"><div class="event-summary-preview"><div><span>Personal spending</span><strong>{{ formatMoney(activeEvent.total_amount) }}</strong><small>Entire event</small></div><div><span>Transactions</span><strong>{{ activeEvent.total_transaction_count }}</strong><small>Exact transaction membership</small></div><div><span>Categories</span><strong>{{ activeEvent.category_count }}</strong><small>Across this event</small></div><div><span>Cards</span><strong>{{ activeEvent.card_count }}</strong><small>Used during this event</small></div></div><div class="event-detail-columns-preview"><section><h3>Spending by category</h3><div class="event-category-list-preview"><button type="button" :class="{ active: activeCategory === 'all' }" @click="activeCategory = 'all'"><i style="background:#aaa8b7"/><span>All categories</span><b>{{ formatMoney(activeEvent.total_amount) }}</b></button><button v-for="(category,index) in categories" :key="category.category" type="button" :class="{ active: activeCategory === category.category }" @click="activeCategory = category.category"><i :style="{ background: colors[index % colors.length] }"/><span>{{ category.category }}</span><b>{{ formatMoney(category.amount) }}</b></button></div></section><section><h3>{{ activeCategory === 'all' ? `All transactions · ${visibleTransactions.length}` : `${activeCategory} · ${visibleTransactions.length}` }}</h3><div class="event-transaction-list-preview"><div v-for="item in visibleTransactions" :key="item.id"><span><strong>{{ item.merchant_display_name || item.merchant_raw }}</strong><small>{{ item.category }}</small></span><span>{{ formatDate(item.transaction_date) }}</span><span>{{ item.provider.toUpperCase() }} •• {{ item.card_last4 }}</span><strong>{{ formatMoney(item.personal_amount) }}</strong></div><p v-if="!visibleTransactions.length">No transactions in this category.</p></div></section></div></template>
    </div></section></div></Teleport>
  <Teleport to="body">
    <div v-if="createOpen" class="event-modal-backdrop-preview" @mousedown.self="closeCreate">
      <section class="event-create-modal-preview" role="dialog" aria-modal="true" aria-labelledby="event-create-title">
        <button type="button" class="event-modal-close-preview" aria-label="Close event creation" @click="closeCreate">×</button>
        <header><h2 id="event-create-title">Create new event</h2><p>Create the event first, then assign individual transactions to it.</p></header>
        <form @submit.prevent="submitCreate">
          <div class="event-create-body-preview">
            <label><span>Name</span><input v-model="createForm.name" required placeholder="For example: Prague 2027" autofocus></label>
            <label><span>Type</span><select v-model="createForm.event_type"><option value="trip">Personal trip</option><option value="business_trip">Business trip</option><option value="celebration">Celebration</option><option value="home">Home project</option><option value="other">Other</option></select></label>
            <label v-if="createForm.event_type === 'business_trip'"><span>Destination</span><input v-model="createForm.destination" required placeholder="For example: City name"><small>Business trips with the same destination are grouped in longer-period views.</small></label>
            <div class="event-create-dates-preview"><label><span>Start date</span><input v-model="createForm.start_date" type="date" required></label><label><span>End date</span><input v-model="createForm.end_date" type="date" required></label></div>
            <label><span>Budget <small>(optional)</small></span><input v-model="createForm.budget" type="number" min="0" step="0.01" placeholder="Not set"></label>
            <label><span>Status</span><select v-model="createForm.status"><option value="planned">Planned</option><option value="active">Active</option><option value="completed">Completed</option></select></label>
            <p v-if="createError" class="event-create-error-preview" role="alert">{{ createError }}</p>
          </div>
          <footer><button type="button" class="secondary" :disabled="createSaving" @click="closeCreate">Cancel</button><button type="submit" class="primary" :disabled="createSaving">{{ createSaving ? 'Creating…' : 'Create event' }}</button></footer>
        </form>
      </section>
    </div>
  </Teleport>
  <Teleport to="body">
    <div v-if="editOpen" class="event-modal-backdrop-preview event-edit-layer-preview" @mousedown.self="closeEdit">
      <section class="event-create-modal-preview" role="dialog" aria-modal="true" aria-labelledby="event-edit-title">
        <button type="button" class="event-modal-close-preview" aria-label="Close event editor" @click="closeEdit">×</button>
        <header><h2 id="event-edit-title">Edit event</h2><p>Update how this event is presented.</p></header>
        <form @submit.prevent="submitEdit">
          <div class="event-create-body-preview">
            <label><span>Name</span><input v-model="editForm.name" required></label>
            <label><span>Type</span><select v-model="editForm.event_type"><option value="trip">Personal trip</option><option value="business_trip">Business trip</option><option value="celebration">Celebration</option><option value="home">Home project</option><option value="other">Other</option></select></label>
            <label v-if="editForm.event_type === 'business_trip'"><span>Destination</span><input v-model="editForm.destination" required placeholder="For example: City name"><small>Business trips with the same destination are grouped in longer-period views.</small></label>
            <div class="event-create-dates-preview"><label><span>Start date</span><input v-model="editForm.start_date" type="date" required></label><label><span>End date</span><input v-model="editForm.end_date" type="date" required></label></div>
            <label><span>Budget <small>(optional)</small></span><input v-model="editForm.budget" type="number" min="0" step="0.01" placeholder="Not set"></label>
            <label><span>Status</span><select v-model="editForm.status"><option value="planned">Planned</option><option value="active">Active</option><option value="completed">Completed</option><option value="cancelled">Cancelled</option></select></label>
            <p v-if="editError" class="event-create-error-preview" role="alert">{{ editError }}</p>
          </div>
          <footer><button type="button" class="secondary" :disabled="editSaving" @click="closeEdit">Close</button><button type="submit" class="primary" :disabled="editSaving">{{ editSaving ? 'Saving…' : 'Save changes' }}</button></footer>
        </form>
      </section>
    </div>
  </Teleport>
  <Teleport to="body"><div v-if="eventNotice" class="event-save-notice-preview" role="status"><span><strong>{{ eventNotice.title }}</strong><small>{{ eventNotice.detail }}</small></span><button type="button" aria-label="Dismiss event message" @click="eventNotice = null">×</button></div></Teleport>
</template>
