<script setup lang="ts">
withDefaults(defineProps<{
  label: string;
  size?: 'regular' | 'compact';
  variant?: 'neutral' | 'accent' | 'danger';
  disabled?: boolean;
}>(), { size: 'regular', variant: 'neutral', disabled: false });
</script>

<template>
  <button class="ui-icon-button" :class="[`ui-icon-button--${size}`, `ui-icon-button--${variant}`]" type="button" :aria-label="label" :disabled="disabled">
    <slot />
  </button>
</template>

<style scoped>
.ui-icon-button{display:grid;place-items:center;padding:0;border:0;background:transparent;color:var(--ui-icon-muted);font:inherit;cursor:pointer}.ui-icon-button--regular{width:34px;height:34px}.ui-icon-button--compact{width:28px;height:28px}.ui-icon-button--accent{color:var(--ui-primary)}.ui-icon-button--danger{color:var(--ui-danger)}.ui-icon-button:focus-visible{outline:2px solid var(--ui-focus);outline-offset:2px}.ui-icon-button:disabled{cursor:not-allowed;opacity:.6}
</style>
