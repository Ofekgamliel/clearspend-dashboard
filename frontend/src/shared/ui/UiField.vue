<script setup lang="ts">
defineProps<{ forId: string; label: string; optional?: boolean; description?: string; error?: string }>();
</script>
<template>
  <label class="ui-field" :for="forId">
    <span class="ui-field__label">{{ label }} <small v-if="optional">(optional)</small></span>
    <slot :description-id="description ? `${forId}-description` : undefined" :error-id="error ? `${forId}-error` : undefined" />
    <small v-if="description" :id="`${forId}-description`" class="ui-field__description">{{ description }}</small>
    <small v-if="error" :id="`${forId}-error`" class="ui-field__error">{{ error }}</small>
  </label>
</template>
<style scoped>
.ui-field{display:block}.ui-field__label{display:block;margin-bottom:5px;color:var(--ui-label);font-size:10px;font-weight:750}.ui-field__label small{color:var(--ui-subtle);font:inherit}.ui-field__description,.ui-field__error{display:block;margin-top:5px;font-size:10px;line-height:1.4}.ui-field__description{color:var(--ui-subtle)}.ui-field__error{color:var(--ui-danger);font-weight:650}
</style>
