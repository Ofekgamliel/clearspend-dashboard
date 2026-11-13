<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { getMerchantReference, saveMerchant } from '../../api/merchants.ts';
import type { MerchantRecord, MerchantReferenceResponse } from '../../api/contracts.ts';
import { formatInteger, formatMoney } from '../../shared/format.ts';
import {
  createMerchantDraft,
  filterMerchants,
  merchantDraftChanged,
  merchantDraftError,
  merchantImpact,
  merchantSaveRequest,
  type MerchantDraft,
  type MerchantReviewFilter,
} from './model.ts';

const emit = defineEmits<{ financialDataChange: [] }>();
const openState = ref(false);
const loading = ref(false);
const error = ref('');
const payload = ref<MerchantReferenceResponse | null>(null);
const search = ref('');
const reviewFilter = ref<MerchantReviewFilter>('all');
const selected = ref<MerchantRecord | null>(null);
const draft = ref<MerchantDraft | null>(null);
const impactReviewed = ref(false);
const saving = ref(false);
const editorError = ref('');
const notice = ref('');

const merchants = computed(() => filterMerchants(payload.value?.merchants ?? [], search.value, reviewFilter.value));
const impact = computed(() => draft.value ? merchantImpact(draft.value) : []);

async function loadMerchants(selectGroup = ''): Promise<void> {
  loading.value = true;
  error.value = '';
  try {
    payload.value = await getMerchantReference();
    if (selectGroup) {
      const refreshed = payload.value.merchants.find((item) => item.canonical_group_id === selectGroup) ?? null;
      if (refreshed) selectMerchant(refreshed);
    }
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : 'Could not load merchants';
  } finally {
    loading.value = false;
  }
}

function open(): void {
  openState.value = true;
  search.value = '';
  reviewFilter.value = 'all';
  notice.value = '';
  void loadMerchants();
}

function close(): void {
  if (saving.value) return;
  openState.value = false;
  selected.value = null;
  draft.value = null;
}

function selectMerchant(merchant: MerchantRecord): void {
  selected.value = merchant;
  draft.value = createMerchantDraft(merchant);
  impactReviewed.value = false;
  editorError.value = '';
  notice.value = '';
}

function markChanged(): void {
  impactReviewed.value = false;
  editorError.value = '';
}

function reviewImpact(): void {
  if (!draft.value) return;
  editorError.value = merchantDraftError(draft.value);
  impactReviewed.value = !editorError.value;
}

async function applyChanges(): Promise<void> {
  if (!draft.value || !impactReviewed.value) return;
  const validation = merchantDraftError(draft.value);
  if (validation) { editorError.value = validation; impactReviewed.value = false; return; }
  saving.value = true;
  editorError.value = '';
  const groupId = draft.value.canonicalGroupId;
  try {
    const response = await saveMerchant(merchantSaveRequest(draft.value));
    emit('financialDataChange');
    await loadMerchants(groupId);
    notice.value = `${response.display_name} saved · ${formatInteger(response.aliases_updated)} aliases · ${formatInteger(response.transactions_updated)} transaction categories updated`;
  } catch (caught) {
    editorError.value = caught instanceof Error ? caught.message : 'Could not save merchant changes';
  } finally {
    saving.value = false;
  }
}

function handleKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape' && openState.value) close();
}

onMounted(() => document.addEventListener('keydown', handleKeydown));
onBeforeUnmount(() => document.removeEventListener('keydown', handleKeydown));
defineExpose({ open });
</script>

<template>
  <Teleport to="body">
    <div v-if="openState" class="merchant-manager-backdrop" @mousedown.self="close">
      <section class="merchant-manager" role="dialog" aria-modal="true" aria-labelledby="merchant-manager-title">
        <button type="button" class="transactions-modal-close" aria-label="Close merchant management" @click="close">×</button>
        <header class="merchant-manager-head">
          <div><p>Data management</p><h2 id="merchant-manager-title">Merchants</h2><span>Manage display identities and permanent categories for exact aliases.</span></div>
          <div v-if="payload" class="merchant-manager-summary"><strong>{{ formatInteger(payload.summary.display_identities) }}</strong><span>identities</span><strong>{{ formatInteger(payload.summary.mapped_aliases) }}</strong><span>aliases</span></div>
        </header>
        <div v-if="error && !payload" class="panel-state error-state"><span>{{ error }}</span><button type="button" @click="loadMerchants()">Try again</button></div>
        <div v-else class="merchant-manager-body" :aria-busy="loading">
          <aside class="merchant-manager-list">
            <label class="merchant-manager-search"><span aria-hidden="true">⌕</span><input v-model="search" type="search" placeholder="Search names and aliases…"></label>
            <div class="merchant-manager-filters" role="group" aria-label="Merchant filters">
              <button type="button" :class="{ active: reviewFilter === 'all' }" @click="reviewFilter = 'all'">All</button>
              <button type="button" :class="{ active: reviewFilter === 'needs_review' }" @click="reviewFilter = 'needs_review'">Needs review</button>
              <button type="button" :class="{ active: reviewFilter === 'mixed_categories' }" @click="reviewFilter = 'mixed_categories'">Mixed</button>
            </div>
            <div class="merchant-manager-list-scroll">
              <button v-for="merchant in merchants" :key="merchant.canonical_group_id" type="button" class="merchant-list-item" :class="{ active: selected?.canonical_group_id === merchant.canonical_group_id }" @click="selectMerchant(merchant)">
                <span><strong>{{ merchant.display_name }}</strong><small>{{ merchant.aliases.length }} aliases · {{ formatInteger(merchant.transactions) }} transactions</small></span>
                <span><b>{{ formatMoney(merchant.amount) }}</b><i v-if="merchant.aliases.some((alias) => alias.category === 'Needs review')">Review</i></span>
              </button>
              <div v-if="!merchants.length && !loading" class="merchant-list-empty">No matching merchants.</div>
            </div>
          </aside>
          <main class="merchant-manager-editor">
            <div v-if="!draft" class="merchant-editor-empty"><strong>Select a merchant</strong><span>Choose a display identity to review its exact statement aliases.</span></div>
            <template v-else>
              <header class="merchant-editor-head">
                <label><span>Display name</span><input v-model="draft.displayName" :disabled="saving" @input="markChanged"></label>
                <div><strong>{{ formatInteger(draft.transactions) }}</strong><span>existing transactions</span></div>
              </header>
              <p class="merchant-editor-scope"><b>Display identity</b> groups these names visually. Each alias keeps its own permanent category.</p>
              <div class="merchant-alias-table-wrap">
                <table class="merchant-alias-table">
                  <thead><tr><th>Original statement name</th><th>Transactions</th><th>Permanent category</th></tr></thead>
                  <tbody><tr v-for="alias in draft.aliases" :key="alias.merchant_normalized">
                    <td><strong>{{ alias.merchant_raw }}</strong><small>{{ alias.merchant_normalized }}</small></td>
                    <td>{{ formatInteger(alias.transactions) }}</td>
                    <td><select v-model="alias.category" :disabled="saving" @change="markChanged"><option v-for="category in payload?.categories ?? []" :key="category" :value="category">{{ category }}</option></select><small v-if="alias.category !== alias.originalCategory" class="merchant-changed-label">Was: {{ alias.originalCategory }}</small></td>
                  </tr></tbody>
                </table>
              </div>
              <section v-if="impactReviewed" class="merchant-impact-review">
                <h3>Review impact</h3>
                <ul><li v-for="item in impact" :key="item">{{ item }}</li></ul>
                <p>Transaction-specific overrides remain unchanged.</p>
              </section>
              <p v-if="editorError" class="transaction-editor-error" role="alert">{{ editorError }}</p>
              <p v-if="notice" class="merchant-save-success" role="status">{{ notice }}</p>
              <footer class="merchant-editor-actions">
                <button type="button" class="secondary" :disabled="saving || !merchantDraftChanged(draft)" @click="reviewImpact">Review impact</button>
                <button type="button" class="primary" :disabled="saving || !impactReviewed" @click="applyChanges">{{ saving ? 'Saving…' : 'Apply changes' }}</button>
              </footer>
            </template>
          </main>
        </div>
      </section>
    </div>
  </Teleport>
</template>
