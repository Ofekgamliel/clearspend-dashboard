<script setup lang="ts">
import { ref } from 'vue';
import { UiButton, UiDialog, UiField, UiIconButton, UiInput, UiSelect } from '../shared/ui';
const dialogOpen = ref(false);
const name = ref('Synthetic event');
const status = ref('planned');
</script>
<template>
  <main class="gallery"><h1>ClearSpend UI gallery</h1><p>Synthetic development states only.</p>
    <section><h2>Buttons</h2><div class="row"><UiButton variant="primary">Primary</UiButton><UiButton>Secondary</UiButton><UiButton variant="danger">Danger</UiButton><UiButton variant="ghost">Ghost</UiButton><UiButton busy>Saving</UiButton><UiButton disabled>Disabled</UiButton><UiIconButton label="Synthetic icon action">×</UiIconButton></div></section>
    <section><h2>Fields</h2><div class="fields"><UiField for-id="gallery-name" label="Name" description="Synthetic content only" v-slot="ids"><UiInput id="gallery-name" v-model="name" :aria-describedby="ids.descriptionId" /></UiField><UiField for-id="gallery-status" label="Status"><UiSelect id="gallery-status" v-model="status"><option value="planned">Planned</option><option value="active">Active</option></UiSelect></UiField></div></section>
    <section><h2>Dialog</h2><UiButton @click="dialogOpen=true">Open compact dialog</UiButton></section>
    <UiDialog :open="dialogOpen" title-id="gallery-dialog-title" close-label="Close synthetic dialog" size="compact" @request-close="dialogOpen=false"><template #header><h2 id="gallery-dialog-title">Synthetic dialog</h2><p>Development-only component state.</p></template><p>No private or production data.</p><template #footer><UiButton @click="dialogOpen=false">Close</UiButton><UiButton variant="primary">Confirm</UiButton></template></UiDialog>
  </main>
</template>
<style scoped>.gallery{max-width:900px;margin:auto;padding:32px}.gallery section{margin-top:24px;padding:20px;border:1px solid var(--ui-border);border-radius:12px;background:var(--ui-surface)}.row{display:flex;flex-wrap:wrap;gap:8px}.fields{display:grid;grid-template-columns:1fr 1fr;gap:12px}</style>
