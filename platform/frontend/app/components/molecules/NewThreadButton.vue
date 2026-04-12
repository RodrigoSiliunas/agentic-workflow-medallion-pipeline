<template>
  <button
    class="w-full flex items-center gap-2 px-3 py-2 rounded-[var(--radius-md)] text-sm font-medium transition-colors border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-elevated)] hover:border-[var(--brand-500)]/40"
    :style="{ color: 'var(--text-primary)' }"
    @click="$emit('click')"
  >
    <AppIcon name="plus" size="sm" class="text-[var(--brand-500)]" />
    <span>Nova conversa</span>
    <span class="ml-auto flex items-center gap-1">
      <AppKbd>Ctrl</AppKbd>
      <AppKbd>N</AppKbd>
    </span>
  </button>
</template>

<script setup lang="ts">
defineEmits<{ click: [] }>()
</script>
