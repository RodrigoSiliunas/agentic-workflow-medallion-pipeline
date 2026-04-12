<template>
  <div
    class="flex items-start gap-2 px-3 py-1 font-[var(--font-mono)] text-[11px] leading-relaxed border-l-2"
    :style="{ borderColor }"
  >
    <span class="tabular-nums flex-shrink-0" :style="{ color: 'var(--text-tertiary)' }">
      {{ timeLabel }}
    </span>
    <AppIcon :name="icon" size="xs" class="mt-0.5 flex-shrink-0" :style="{ color: borderColor }" />
    <span class="flex-1 break-all" :style="{ color: 'var(--text-secondary)' }">
      {{ log.message }}
    </span>
  </div>
</template>

<script setup lang="ts">
import type { LogEntry } from "~/types/deployment"

const props = defineProps<{ log: LogEntry }>()

const levelColors: Record<string, string> = {
  info: "var(--text-tertiary)",
  debug: "var(--text-tertiary)",
  warn: "var(--status-warning)",
  error: "var(--status-error)",
  success: "var(--status-success)",
}

const levelIcons: Record<string, string> = {
  info: "information-circle",
  debug: "bug-ant",
  warn: "exclamation-triangle",
  error: "x-circle",
  success: "check-circle",
}

const borderColor = computed(() => levelColors[props.log.level] ?? "var(--border)")
const icon = computed(() => levelIcons[props.log.level] ?? "information-circle")

const timeLabel = computed(() => {
  try {
    return new Date(props.log.timestamp).toLocaleTimeString("pt-BR", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    })
  } catch {
    return ""
  }
})
</script>
