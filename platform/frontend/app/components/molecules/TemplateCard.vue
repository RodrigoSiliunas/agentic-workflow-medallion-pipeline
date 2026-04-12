<template>
  <NuxtLink
    :to="`/marketplace/${template.slug}`"
    class="group block rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-elevated)] hover:border-[var(--brand-500)]/50 transition-all p-5 h-full"
  >
    <div class="flex items-start gap-3 mb-3">
      <div
        class="w-10 h-10 rounded-[var(--radius-md)] flex items-center justify-center flex-shrink-0"
        :style="{ background: template.iconBg }"
      >
        <AppIcon :name="template.icon" size="md" class="text-white" />
      </div>
      <div class="min-w-0 flex-1">
        <h3
          class="text-sm font-semibold truncate tracking-tight group-hover:text-[var(--brand-500)] transition-colors"
          :style="{ color: 'var(--text-primary)' }"
        >
          {{ template.name }}
        </h3>
        <p class="text-[11px] truncate" :style="{ color: 'var(--text-tertiary)' }">
          v{{ template.version }} · {{ template.author }}
        </p>
      </div>
    </div>

    <p
      class="text-xs leading-relaxed mb-4 line-clamp-3"
      :style="{ color: 'var(--text-secondary)' }"
    >
      {{ template.tagline }}
    </p>

    <div class="flex flex-wrap gap-1 mb-4">
      <TagPill v-for="tag in visibleTags" :key="tag" tone="neutral">
        {{ tag }}
      </TagPill>
      <TagPill v-if="hiddenCount > 0" tone="neutral">+{{ hiddenCount }}</TagPill>
    </div>

    <div
      class="flex items-center justify-between text-[11px] pt-3 border-t"
      :style="{ color: 'var(--text-tertiary)', borderColor: 'var(--border)' }"
    >
      <span class="inline-flex items-center gap-1">
        <AppIcon name="rocket-launch" size="xs" />
        {{ template.deployCount }} deploys
      </span>
      <span class="inline-flex items-center gap-1">
        <AppIcon name="clock" size="xs" />
        {{ template.durationEstimate }}
      </span>
    </div>
  </NuxtLink>
</template>

<script setup lang="ts">
import type { Template } from "~/types/template"

const props = defineProps<{ template: Template }>()

const MAX_VISIBLE_TAGS = 4
const visibleTags = computed(() => props.template.tags.slice(0, MAX_VISIBLE_TAGS))
const hiddenCount = computed(() => Math.max(0, props.template.tags.length - MAX_VISIBLE_TAGS))
</script>
