<script setup lang="ts">
withDefaults(defineProps<{
  type?: 'button' | 'submit' | 'reset';
  variant?: 'primary' | 'secondary' | 'soft-accent' | 'danger' | 'ghost';
  size?: 'compact' | 'regular';
  disabled?: boolean;
  busy?: boolean;
}>(), { type: 'button', variant: 'secondary', size: 'regular', disabled: false, busy: false });
</script>

<template><button class="ui-button" :class="[`ui-button--${variant}`, `ui-button--${size}`]" :type="type" :disabled="disabled || busy" :aria-busy="busy || undefined"><i v-if="busy" aria-hidden="true"/><span><slot/></span></button></template>

<style scoped>
.ui-button{display:inline-flex;align-items:center;justify-content:center;gap:7px;border:1px solid transparent;border-radius:8px;font:750 10px/1 inherit;cursor:pointer}.ui-button--regular{min-height:34px;padding:0 12px}.ui-button--compact{min-height:30px;padding:0 10px}.ui-button:focus-visible{outline:2px solid var(--ui-focus);outline-offset:2px}.ui-button:disabled{cursor:not-allowed;opacity:.6}.ui-button--primary{border-color:var(--ui-primary);background:var(--ui-primary);color:var(--ui-on-primary)}.ui-button--secondary{border-color:var(--ui-button-border);background:var(--ui-surface);color:var(--ui-muted)}.ui-button--soft-accent{border-color:var(--ui-accent-border);background:var(--ui-accent-soft);color:var(--ui-accent-text)}.ui-button--soft-accent:not(:disabled):hover{border-color:var(--ui-accent-border-hover);background:var(--ui-accent-soft-hover)}.ui-button--danger{border-color:var(--ui-danger-border);background:var(--ui-surface);color:var(--ui-danger)}.ui-button--ghost{background:transparent;color:var(--ui-primary)}.ui-button i{width:11px;height:11px;border:2px solid currentColor;border-right-color:transparent;border-radius:50%;animation:spin .7s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}@media(prefers-reduced-motion:reduce){.ui-button i{animation:none}}
</style>
