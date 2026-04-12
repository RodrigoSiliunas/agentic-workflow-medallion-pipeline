<template>
  <div class="flex flex-col items-center justify-center text-center py-12 px-6">
    <div
      v-if="icon"
      class="w-12 h-12 rounded-full bg-[var(--surface-elevated)] border border-[var(--border)] flex items-center justify-center mb-4"
    >
      <AppIcon :name="icon" size="lg" class="text-[var(--text-tertiary)]" />
    </div>
    <h3
      v-if="title"
      class="text-base font-semibold mb-1.5"
      :style="{ color: 'var(--text-primary)' }"
    >
      {{ title }}
    </h3>
    <p
      v-if="description"
      class="text-sm max-w-sm leading-relaxed"
      :style="{ color: 'var(--text-secondary)' }"
    >
      {{ description }}
    </p>
    <div v-if="$slots.default" class="mt-6">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  icon?: string
  title?: string
  description?: string
}>()
</script>
