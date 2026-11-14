<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue';

export type ManagementTarget = 'import' | 'audit' | 'merchants';
const emit = defineEmits<{ select: [target: ManagementTarget] }>();
const open = ref(false);
const wrap = ref<HTMLElement | null>(null);
const button = ref<HTMLButtonElement | null>(null);

function select(target: ManagementTarget): void {
  open.value = false;
  emit('select', target);
}

function handlePointerDown(event: PointerEvent): void {
  if (open.value && !wrap.value?.contains(event.target as Node)) open.value = false;
}

function handleKeydown(event: KeyboardEvent): void {
  if (event.key !== 'Escape' || !open.value) return;
  open.value = false;
  void nextTick(() => button.value?.focus());
}

onMounted(() => {
  document.addEventListener('pointerdown', handlePointerDown);
  document.addEventListener('keydown', handleKeydown);
});
onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', handlePointerDown);
  document.removeEventListener('keydown', handleKeydown);
});
</script>

<template>
  <div ref="wrap" class="app-manage-wrap">
    <button ref="button" type="button" class="app-manage-button" aria-label="Manage data" title="Manage data" :aria-expanded="open" aria-haspopup="menu" @click="open = !open"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h10M18 7h2M4 17h2M10 17h10M14 4v6M6 14v6"/><circle cx="14" cy="7" r="2.5"/><circle cx="8" cy="17" r="2.5"/></svg></button>
    <div v-if="open" class="app-manage-menu" role="menu">
      <button type="button" role="menuitem" @click="select('import')"><b>⇧</b><span><strong>Import statements</strong><small>Stage, review and reconcile files</small></span></button>
      <button type="button" role="menuitem" @click="select('audit')"><b>≡</b><span><strong>Import history</strong><small>Coverage, inserted rows and duplicates</small></span></button>
      <button type="button" role="menuitem" @click="select('merchants')"><b>◎</b><span><strong>Merchants</strong><small>Display names and permanent categories</small></span></button>
    </div>
  </div>
</template>
