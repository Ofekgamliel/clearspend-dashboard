<script setup lang="ts">
withDefaults(defineProps<{
  as?: 'article' | 'section';
  density?: 'standard' | 'compact';
}>(), { as: 'article', density: 'standard' });
</script>

<template>
  <component :is="as" class="ui-panel" :class="`ui-panel--${density}`">
    <slot name="header" />
    <slot />
  </component>
</template>

<style scoped>
.ui-panel{width:100%;border:1px solid var(--ui-panel-border);border-radius:14px;background:var(--ui-surface);box-shadow:0 9px 30px var(--ui-panel-shadow)}.ui-panel--standard{padding:19px}.ui-panel--compact{padding:15px 20px}
</style>
