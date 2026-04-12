<template>
  <div class="inline-flex items-center gap-1.5">
    <span
      class="inline-block w-1.5 h-1.5 rounded-full"
      :class="{ 'status-pulse': status === 'RUNNING' }"
      :style="{ background: dotColor }"
    />
    <span
      class="text-[11px] font-medium tracking-tight"
      :style="{ color: 'var(--text-secondary)' }"
    >
      {{ label }}
    </span>
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
  SUCCESS: "Ativo",
  FAILED: "Falhou",
  RUNNING: "Rodando",
  IDLE: "Parado",
  RECOVERED: "Recuperado",
}

const dotColor = computed(() => colorMap[props.status] || "var(--text-tertiary)")
const label = computed(() => labelMap[props.status] || props.status)
</script>
