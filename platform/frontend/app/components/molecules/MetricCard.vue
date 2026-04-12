<template>
  <div
    class="rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)] p-4"
  >
    <div class="flex items-center gap-2 mb-2">
      <AppIcon :name="icon" size="sm" :style="{ color: iconColor }" />
      <p
        class="text-[10px] uppercase tracking-wider font-medium"
        :style="{ color: 'var(--text-tertiary)' }"
      >
        {{ label }}
      </p>
    </div>
    <p class="text-xl font-semibold tracking-tight" :style="{ color: 'var(--text-primary)' }">
      {{ value }}
    </p>
    <p v-if="hint" class="text-[11px] mt-0.5" :style="{ color: 'var(--text-secondary)' }">
      {{ hint }}
    </p>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    label: string
    value: string | number
    icon: string
    iconColor?: string
    hint?: string
  }>(),
  {
    iconColor: "var(--brand-500)",
    hint: undefined,
  },
)
</script>
