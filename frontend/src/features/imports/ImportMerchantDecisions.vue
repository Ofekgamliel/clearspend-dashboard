<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue';
import type { DisplayIdentityReference, ImportMerchantDecision, StagedMerchant } from '../../api/contracts.ts';
import { formatDate, formatMoney } from '../../shared/format.ts';
import { UiSelect } from '../../shared/ui';
import { rankedIdentityMatches } from './model.ts';

const props = defineProps<{
  merchants: StagedMerchant[];
  decisions: Map<string, ImportMerchantDecision>;
  categories: string[];
  identities: DisplayIdentityReference[];
}>();
const emit = defineEmits<{
  update: [key: string, field: keyof ImportMerchantDecision, value: string];
  identity: [key: string, identity: DisplayIdentityReference];
  createIdentity: [key: string, displayName: string];
}>();

const activeKey = ref('');
const activeInput = ref<HTMLInputElement | null>(null);
const menu = ref<HTMLElement | null>(null);
const menuStyle = ref<Record<string, string>>({});
const query = ref('');
const invalidCount = computed(() => props.merchants.filter((merchant) => {
  const decision = props.decisions.get(merchant.merchant_normalized);
  return decision && !['needs_review', 'exclude'].includes(decision.resolution)
    && (!decision.category || decision.category === 'Needs review' || (decision.resolution === 'link' && !decision.canonical_group_id));
}).length);
const activeMerchant = computed(() => props.merchants.find((item) => item.merchant_normalized === activeKey.value) ?? null);
const activeDecision = computed(() => activeKey.value ? props.decisions.get(activeKey.value) ?? null : null);
const choices = computed(() => rankedIdentityMatches(query.value, props.identities).slice(0, 8));
const categoryOptions = (decision: ImportMerchantDecision) => [...new Set([...props.categories, decision.category, 'Needs review'].filter(Boolean))];

function categorySummary(identity: DisplayIdentityReference): string {
  if (identity.category_status === 'unanimous') return `${identity.category} · all ${identity.categories[0]?.aliases ?? identity.aliases} mapped aliases`;
  if (identity.category_status === 'mixed') return `Mixed categories · ${identity.categories.map((item) => `${item.category} (${item.aliases})`).join(' · ')}`;
  return 'No approved category for existing aliases';
}
function closeMenu(): void { activeKey.value = ''; activeInput.value = null; }
async function openMenu(event: Event, merchant: StagedMerchant): Promise<void> {
  activeInput.value = event.currentTarget as HTMLInputElement;
  activeKey.value = merchant.merchant_normalized;
  query.value = activeDecision.value?.display_name ?? merchant.merchant_raw;
  await nextTick();
  positionMenu();
}
function positionMenu(): void {
  if (!activeInput.value || !menu.value) return;
  const rect = activeInput.value.getBoundingClientRect();
  const width = Math.max(rect.width, 310);
  const gap = 5;
  const desiredHeight = Math.min(menu.value.scrollHeight || 240, 240);
  const spaceBelow = window.innerHeight - rect.bottom - gap;
  const openUp = spaceBelow < Math.min(desiredHeight, 150) && rect.top > spaceBelow;
  menuStyle.value = {
    width: `${width}px`,
    left: `${Math.min(Math.max(10, rect.left), window.innerWidth - width - 10)}px`,
    top: `${openUp ? Math.max(10, rect.top - gap - desiredHeight) : rect.bottom + gap}px`,
  };
}
function updateDisplay(event: Event, merchant: StagedMerchant): void {
  const value = (event.currentTarget as HTMLInputElement).value;
  query.value = value;
  emit('update', merchant.merchant_normalized, 'display_name', value);
  if (activeKey.value !== merchant.merchant_normalized) void openMenu(event, merchant);
  else void nextTick(positionMenu);
}
function selectIdentity(identity: DisplayIdentityReference): void {
  if (!activeKey.value) return;
  emit('identity', activeKey.value, identity);
  closeMenu();
}
function createIdentity(): void {
  if (!activeKey.value || !activeMerchant.value) return;
  emit('createIdentity', activeKey.value, activeMerchant.value.merchant_raw);
  closeMenu();
}
function handleDocumentClick(event: MouseEvent): void {
  const target = event.target as Node;
  if (activeInput.value?.contains(target) || menu.value?.contains(target)) return;
  closeMenu();
}
function handleKeydown(event: KeyboardEvent): void { if (event.key === 'Escape') closeMenu(); }
onMounted(() => {
  document.addEventListener('mousedown', handleDocumentClick);
  document.addEventListener('keydown', handleKeydown);
  window.addEventListener('resize', positionMenu);
  window.addEventListener('scroll', positionMenu, true);
});
onBeforeUnmount(() => {
  document.removeEventListener('mousedown', handleDocumentClick);
  document.removeEventListener('keydown', handleKeydown);
  window.removeEventListener('resize', positionMenu);
  window.removeEventListener('scroll', positionMenu, true);
});
</script>

<template>
  <div class="import-callout" :class="{ warning: invalidCount }">
    <strong>{{ invalidCount ? `${invalidCount} permanent decision${invalidCount === 1 ? '' : 's'} still need attention.` : 'Every suggestion remains editable.' }}</strong>
    Link an exact statement name to an existing identity, create a new permanent rule, keep the decision in this batch only, or defer it safely.
  </div>
  <div class="import-table-wrap merchant-decisions">
    <table>
      <thead><tr><th>Merchant</th><th>Context</th><th>Resolution</th><th>Category</th><th>Display name</th><th>Apply to</th></tr></thead>
      <tbody>
        <tr v-for="merchant in merchants" :key="merchant.merchant_normalized" :class="{ deferred: decisions.get(merchant.merchant_normalized)?.resolution === 'needs_review', excluded: decisions.get(merchant.merchant_normalized)?.resolution === 'exclude' }">
          <td>
            <strong>{{ merchant.merchant_raw }}</strong>
            <small>{{ merchant.transactions }} transaction{{ merchant.transactions === 1 ? '' : 's' }} · {{ formatMoney(merchant.amount) }}</small>
            <small v-if="decisions.get(merchant.merchant_normalized)?.suggested_match" class="identity-suggestion">Suggested match: {{ decisions.get(merchant.merchant_normalized)?.display_name }}</small>
          </td>
          <td><strong>{{ merchant.providers.join(', ').toUpperCase() }}</strong><small>{{ formatDate(merchant.first_date) }} – {{ formatDate(merchant.last_date) }}</small></td>
          <td><UiSelect :model-value="decisions.get(merchant.merchant_normalized)?.resolution ?? ''" density="dense" @update:model-value="emit('update', merchant.merchant_normalized, 'resolution', $event)"><option value="create">Create new rule</option><option value="link">Link existing merchant</option><option v-if="merchant.provider_category" value="provider">Use provider value</option><option value="needs_review">Needs review</option><option value="exclude">Exclude rows</option></UiSelect></td>
          <td><UiSelect :model-value="decisions.get(merchant.merchant_normalized)?.category ?? ''" density="dense" :disabled="decisions.get(merchant.merchant_normalized)?.resolution === 'exclude'" @update:model-value="emit('update', merchant.merchant_normalized, 'category', $event)"><option v-for="category in categoryOptions(decisions.get(merchant.merchant_normalized)!)" :key="category">{{ category }}</option></UiSelect></td>
          <td>
            <input
              :value="decisions.get(merchant.merchant_normalized)?.display_name"
              :disabled="decisions.get(merchant.merchant_normalized)?.resolution === 'exclude'"
              autocomplete="off"
              role="combobox"
              aria-autocomplete="list"
              :aria-expanded="activeKey === merchant.merchant_normalized"
              aria-label="Search existing display names or enter a new one"
              @focus="openMenu($event, merchant)"
              @input="updateDisplay($event, merchant)"
            >
          </td>
          <td><UiSelect :model-value="decisions.get(merchant.merchant_normalized)?.scope ?? ''" density="dense" :disabled="['link', 'exclude'].includes(decisions.get(merchant.merchant_normalized)?.resolution ?? '')" :title="decisions.get(merchant.merchant_normalized)?.resolution === 'link' ? 'This exact statement name will be linked permanently.' : 'Choose whether the decision applies to future exact matches.'" @update:model-value="emit('update', merchant.merchant_normalized, 'scope', $event)"><option value="exact">This name, future too</option><option v-if="decisions.get(merchant.merchant_normalized)?.resolution !== 'link'" value="batch">This batch only</option></UiSelect></td>
        </tr>
      </tbody>
    </table>
  </div>
  <Teleport to="body">
    <div v-if="activeKey" ref="menu" class="identity-combobox-menu" :style="menuStyle" role="listbox">
      <button v-for="(choice, index) in choices" :key="choice.identity.canonical_group_id" type="button" role="option" @mousedown.prevent="selectIdentity(choice.identity)">
        <strong>{{ choice.identity.display_name }} <em v-if="index === 0 && choice.score >= 70">Suggested match</em></strong>
        <small>{{ choice.identity.aliases }} aliases · {{ choice.identity.transactions }} transactions</small>
        <small :class="{ mixed: choice.identity.category_status === 'mixed' }">{{ categorySummary(choice.identity) }}</small>
      </button>
      <button v-if="activeMerchant" type="button" class="create-identity" @mousedown.prevent="createIdentity">Use “{{ activeMerchant.merchant_raw }}” as a new display name</button>
      <p v-if="!choices.length && !activeMerchant">No matching display names</p>
    </div>
  </Teleport>
</template>
