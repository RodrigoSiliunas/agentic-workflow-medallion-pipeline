<template>
  <div class="help-card">
    <h3 class="text-sm font-semibold mb-1" :style="{ color: 'var(--text-primary)' }">
      {{ title }}
    </h3>
    <p class="text-xs mb-2" :style="{ color: 'var(--text-secondary)' }">
      {{ description }}
    </p>
    <ul class="space-y-1 mb-2">
      <li
        v-for="(item, i) in items"
        :key="i"
        class="flex items-start gap-2 text-xs"
        :style="{ color: 'var(--text-secondary)' }"
      >
        <AppIcon name="check" size="xs" class="text-[var(--status-success)] mt-0.5 flex-shrink-0" />
        <span>{{ item }}</span>
      </li>
    </ul>
    <div
      v-if="warning"
      class="flex items-start gap-2 px-3 py-2 rounded-[var(--radius-md)] mb-2"
      :style="{ background: 'rgba(251,191,36,0.1)', border: '1px solid rgba(251,191,36,0.25)' }"
    >
      <AppIcon name="exclamation-triangle" size="sm" class="text-[var(--status-warning)] flex-shrink-0 mt-0.5" />
      <p class="text-[11px]" :style="{ color: 'rgb(251,191,36)' }">
        {{ warning }}
      </p>
    </div>
    <a
      v-if="link"
      :href="link"
      target="_blank"
      rel="noopener"
      class="inline-flex items-center gap-1 text-xs"
      :style="{ color: 'var(--brand-400)' }"
    >
      <AppIcon name="arrow-top-right-on-square" size="xs" />
      {{ linkText }}
    </a>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    title: string
    description: string
    items: string[]
    link?: string
    linkText?: string
    warning?: string
  }>(),
  {
    link: undefined,
    linkText: "Documentacao",
    warning: undefined,
  },
)
</script>

<style scoped>
.help-card {
  padding: 1rem;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
  background: var(--surface);
}
</style>
