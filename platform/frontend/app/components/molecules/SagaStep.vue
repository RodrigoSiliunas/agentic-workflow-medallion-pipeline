<template>
  <div
    class="flex items-start gap-3 px-4 py-3 rounded-[var(--radius-md)] border transition-colors"
    :style="{
      background: step.status === 'running' ? 'var(--surface-elevated)' : 'var(--surface)',
      borderColor: borderColor,
    }"
  >
    <div class="mt-0.5 flex-shrink-0">
      <span
        v-if="step.status === 'running'"
        class="block w-5 h-5 rounded-full border-2 border-[var(--brand-500)] border-t-transparent animate-spin"
      />
      <div
        v-else
        class="w-5 h-5 rounded-full flex items-center justify-center"
        :style="{ background: iconBg }"
      >
        <AppIcon v-if="step.status === 'success'" name="check" size="xs" class="text-white" />
        <AppIcon v-else-if="step.status === 'failed'" name="x-mark" size="xs" class="text-white" />
        <AppIcon
          v-else-if="step.status === 'skipped'"
          name="minus"
          size="xs"
          class="text-white"
        />
        <span v-else class="text-[10px]" :style="{ color: 'var(--text-tertiary)' }">
          {{ index + 1 }}
        </span>
      </div>
    </div>

    <div class="flex-1 min-w-0">
      <div class="flex items-center justify-between gap-2">
        <h4 class="text-sm font-medium tracking-tight" :style="{ color: textColor }">
          {{ step.name }}
        </h4>
        <span
          v-if="step.durationMs"
          class="text-[10px] tabular-nums"
          :style="{ color: 'var(--text-tertiary)' }"
        >
          {{ formatDuration(step.durationMs) }}
        </span>
      </div>
      <p
        v-if="step.description"
        class="text-[11px] mt-0.5"
        :style="{ color: 'var(--text-tertiary)' }"
      >
        {{ step.description }}
      </p>
      <p
        v-if="step.errorMessage"
        class="text-[11px] mt-1 font-[var(--font-mono)]"
        :style="{ color: 'var(--status-error)' }"
      >
        {{ step.errorMessage }}
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { SagaStepState } from "~/types/deployment"

const props = defineProps<{
  step: SagaStepState
  index: number
}>()

const borderColor = computed(() => {
  switch (props.step.status) {
    case "running":
      return "var(--brand-500)"
    case "success":
      return "var(--border)"
    case "failed":
      return "var(--status-error)"
    default:
      return "var(--border)"
  }
})

const iconBg = computed(() => {
  switch (props.step.status) {
    case "success":
      return "var(--status-success)"
    case "failed":
      return "var(--status-error)"
    case "skipped":
      return "var(--text-tertiary)"
    default:
      return "var(--surface-elevated)"
  }
})

const textColor = computed(() =>
  props.step.status === "pending" ? "var(--text-tertiary)" : "var(--text-primary)",
)

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}
</script>
