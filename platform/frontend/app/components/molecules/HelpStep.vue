<template>
  <div class="flex gap-3">
    <div
      class="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 text-[10px] font-bold"
      :style="{ background: 'var(--brand-600)', color: 'white' }"
    >
      {{ number }}
    </div>
    <div class="flex-1 min-w-0">
      <div class="flex items-center gap-2">
        <h4 class="text-xs font-semibold" :style="{ color: 'var(--text-primary)' }">
          {{ title }}
        </h4>
        <span
          class="text-[10px] px-1.5 py-0.5 rounded-full"
          :style="{ background: 'var(--surface-elevated)', color: 'var(--text-tertiary)' }"
        >
          {{ duration }}
        </span>
      </div>
      <p class="text-[11px] mt-0.5" :style="{ color: 'var(--text-secondary)' }">
        <slot />
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  number: string
  title: string
  duration: string
}>()
</script>
