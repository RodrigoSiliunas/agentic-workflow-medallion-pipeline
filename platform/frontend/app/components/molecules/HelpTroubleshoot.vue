<template>
  <div
    class="px-4 py-3 rounded-[var(--radius-lg)] border"
    :style="{ borderColor: 'var(--border)', background: 'var(--surface)' }"
  >
    <div class="flex items-start gap-2">
      <AppIcon name="x-circle" size="sm" class="text-[var(--status-error)] flex-shrink-0 mt-0.5" />
      <div>
        <p class="text-xs font-mono font-medium mb-1" :style="{ color: 'var(--status-error)' }">
          {{ error }}
        </p>
        <p class="text-xs" :style="{ color: 'var(--text-secondary)' }">
          {{ solution }}
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  error: string
  solution: string
}>()
</script>
