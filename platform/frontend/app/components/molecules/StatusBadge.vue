<template>
  <div class="flex items-center gap-1.5">
    <span
      class="inline-block w-2 h-2 rounded-full"
      :class="{ 'animate-pulse': status === 'RUNNING' }"
      :style="{ background: dotColor }"
    />
    <span class="text-xs" :style="{ color: 'var(--text-secondary)' }">{{ label }}</span>
  </div>
</template>

<script setup lang="ts">
import type { PipelineStatus } from "~/types/pipeline"

const props = defineProps<{ status: PipelineStatus }>()

const colorMap: Record<PipelineStatus, string> = {
  SUCCESS: "var(--status-success)",
  FAILED: "var(--status-error)",
  RUNNING: "var(--status-warning)",
  IDLE: "var(--text-tertiary)",
  RECOVERED: "var(--status-info)",
}

const labelMap: Record<PipelineStatus, string> = {
  SUCCESS: "OK",
  FAILED: "Falhou",
  RUNNING: "Rodando",
  IDLE: "Parado",
  RECOVERED: "Recuperado",
}

const dotColor = computed(() => colorMap[props.status] || "var(--text-tertiary)")
const label = computed(() => labelMap[props.status] || props.status)
</script>
