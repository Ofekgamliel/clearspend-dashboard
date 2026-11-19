<script setup lang="ts">
import { ref } from 'vue';
import { UiButton, UiDialog, UiField, UiIconButton, UiInput, UiPanel, UiSelect } from '../shared/ui';
const dialogOpen = ref(false);
const dialogSize = ref<'compact' | 'medium' | 'wide' | 'standard' | 'insight' | 'large' | 'browser' | 'analysis' | 'management'>('compact');
const name = ref('Synthetic event');
const status = ref('planned');
function openDialog(size: 'compact' | 'medium' | 'wide' | 'standard' | 'insight' | 'large' | 'browser' | 'analysis' | 'management'): void { dialogSize.value = size; dialogOpen.value = true; }
</script>
<template>
  <main class="gallery"><h1>ClearSpend UI gallery</h1><p>Synthetic development states only.</p>
    <section><h2>Buttons</h2><div class="row"><UiButton variant="primary">Primary</UiButton><UiButton>Secondary</UiButton><UiButton variant="soft-accent">Soft accent</UiButton><UiButton variant="soft-accent" size="compact">Compact accent</UiButton><UiButton variant="danger">Danger</UiButton><UiButton variant="ghost">Ghost</UiButton><UiButton busy>Saving</UiButton><UiButton disabled>Disabled</UiButton><UiIconButton label="Synthetic icon action">×</UiIconButton></div></section>
    <section><h2>Fields</h2><div class="fields"><UiField for-id="gallery-name" label="Name" description="Synthetic content only" v-slot="ids"><UiInput id="gallery-name" v-model="name" :aria-describedby="ids.descriptionId" /></UiField><UiField for-id="gallery-status" label="Status"><UiSelect id="gallery-status" v-model="status"><option value="planned">Planned</option><option value="active">Active</option></UiSelect></UiField><UiField for-id="gallery-dense" label="Dense field"><UiInput id="gallery-dense" v-model="name" density="dense" /></UiField><UiField for-id="gallery-dense-select" label="Dense select"><UiSelect id="gallery-dense-select" v-model="status" density="dense"><option value="planned">Planned</option><option value="active">Active</option></UiSelect></UiField></div></section>
    <section><h2>Dialog</h2><div class="row"><UiButton @click="openDialog('compact')">Open compact dialog</UiButton><UiButton @click="openDialog('medium')">Open medium dialog</UiButton><UiButton @click="openDialog('wide')">Open wide dialog</UiButton><UiButton @click="openDialog('standard')">Open standard dialog</UiButton><UiButton @click="openDialog('insight')">Open insight dialog</UiButton><UiButton @click="openDialog('large')">Open large dialog</UiButton><UiButton @click="openDialog('browser')">Open browser dialog</UiButton><UiButton @click="openDialog('analysis')">Open analysis dialog</UiButton><UiButton @click="openDialog('management')">Open management dialog</UiButton></div></section>
    <UiPanel aria-labelledby="gallery-panel-title"><template #header><h2 id="gallery-panel-title">Panel</h2></template><p>Synthetic read-only panel content.</p></UiPanel>
    <UiDialog :open="dialogOpen" title-id="gallery-dialog-title" close-label="Close synthetic dialog" :size="dialogSize" @request-close="dialogOpen=false"><template #header><h2 id="gallery-dialog-title">Synthetic {{ dialogSize }} dialog</h2><p>Development-only component state.</p></template><p>No private or production data.</p><template #footer><UiButton @click="dialogOpen=false">Close</UiButton><UiButton variant="primary">Confirm</UiButton></template></UiDialog>
  </main>
</template>
<style scoped>.gallery{max-width:900px;margin:auto;padding:32px}.gallery section{margin-top:24px;padding:20px;border:1px solid var(--ui-border);border-radius:12px;background:var(--ui-surface)}.row{display:flex;flex-wrap:wrap;gap:8px}.fields{display:grid;grid-template-columns:1fr 1fr;gap:12px}</style>
