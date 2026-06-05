<template>
  <div class="flex items-center justify-between gap-3">
    <div class="flex min-w-0 flex-col gap-0.5">
      <div
        v-if="overline"
        class="text-[10px] font-semibold uppercase tracking-[0.08em]"
        :style="{ color: 'var(--fg-tertiary)' }"
      >
        {{ overline }}
      </div>
      <div
        v-if="title"
        class="text-[13px] font-semibold tracking-[-0.01em]"
        :style="{ color: 'var(--fg-primary)' }"
      >
        {{ title }}
      </div>
    </div>
    <!-- Slot para ação opcional (botão, kebab, etc.) -->
    <slot name="action" />
  </div>
</template>

<script setup lang="ts">
defineProps<{
  overline?: string
  title?: string
}>()
</script>
