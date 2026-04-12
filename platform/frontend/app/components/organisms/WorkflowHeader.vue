<template>
  <header
    class="flex items-center justify-between gap-3 px-6 py-3 border-b"
    :style="{ borderColor: 'var(--border)' }"
  >
    <div class="flex items-center gap-3 min-w-0">
      <div
        class="w-8 h-8 rounded-[var(--radius-md)] flex items-center justify-center flex-shrink-0"
        :style="{ background: 'var(--brand-600)' }"
      >
        <AppIcon name="cpu-chip" size="sm" class="text-white" />
      </div>
      <div class="min-w-0">
        <div class="flex items-center gap-2">
          <h2
            class="text-sm font-semibold truncate"
            :style="{ color: 'var(--text-primary)' }"
          >
            {{ pipeline?.name ?? "Pipeline" }}
          </h2>
          <StatusBadge v-if="pipeline" :status="pipeline.status" />
        </div>
        <p
          v-if="threadTitle"
          class="text-[11px] truncate"
          :style="{ color: 'var(--text-tertiary)' }"
        >
          {{ threadTitle }}
        </p>
      </div>
    </div>

    <div class="flex items-center gap-1 flex-shrink-0">
      <AppButton variant="ghost" size="sm" icon="i-heroicons-arrow-path" square />
      <AppButton variant="ghost" size="sm" icon="i-heroicons-ellipsis-horizontal" square />
    </div>
  </header>
</template>

<script setup lang="ts">
import type { Pipeline } from "~/types/pipeline"

defineProps<{
  pipeline: Pipeline | null
  threadTitle?: string
}>()
</script>
