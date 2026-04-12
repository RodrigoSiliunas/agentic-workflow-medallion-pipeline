<template>
  <button
    class="w-full text-left rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-elevated)] transition-colors p-4"
    @click="$emit('select', pipeline.id)"
  >
    <div class="flex items-start justify-between gap-3 mb-2">
      <h3 class="text-sm font-semibold truncate" :style="{ color: 'var(--text-primary)' }">
        {{ pipeline.name }}
      </h3>
      <StatusBadge :status="pipeline.status" />
    </div>
    <div class="flex items-center gap-4 text-[11px]" :style="{ color: 'var(--text-tertiary)' }">
      <span class="inline-flex items-center gap-1">
        <AppIcon name="chat-bubble-left-right" size="xs" />
        {{ pipeline.threadCount }} conversas
      </span>
      <span v-if="pipeline.lastRunAt" class="inline-flex items-center gap-1">
        <AppIcon name="clock" size="xs" />
        {{ relativeTime(pipeline.lastRunAt) }}
      </span>
    </div>
  </button>
</template>

<script setup lang="ts">
import type { Pipeline } from "~/types/pipeline"

defineProps<{ pipeline: Pipeline }>()
defineEmits<{ select: [id: string] }>()

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return "agora"
  if (minutes < 60) return `${minutes}min atrás`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h atrás`
  const days = Math.floor(hours / 24)
  return `${days}d atrás`
}
</script>
