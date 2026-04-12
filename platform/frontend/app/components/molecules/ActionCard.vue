<template>
  <div
    class="flex items-center gap-2 px-3 py-2 rounded-[var(--radius-md)] text-[11px] border border-[var(--border)] bg-[var(--surface-elevated)]"
    :style="{ borderLeft: `3px solid ${accentColor}` }"
  >
    <AppIcon :name="iconName" size="sm" :style="{ color: accentColor }" />
    <span class="flex-1" :style="{ color: 'var(--text-secondary)' }">{{ label }}</span>
    <a
      v-if="linkUrl"
      :href="linkUrl"
      target="_blank"
      rel="noopener"
      class="underline font-medium"
      :style="{ color: 'var(--brand-500)' }"
    >
      {{ linkLabel }}
    </a>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  action: {
    type?: string
    action?: string
    status?: string
    details?: Record<string, unknown>
  }
}>()

const actionType = computed(() => props.action.action || props.action.type || "unknown")

const config: Record<string, { icon: string; color: string; label: string }> = {
  create_pull_request: { icon: "code-bracket", color: "var(--brand-500)", label: "PR criado" },
  pr_created: { icon: "code-bracket", color: "var(--brand-500)", label: "PR criado" },
  trigger_pipeline_run: { icon: "play", color: "var(--status-warning)", label: "Run disparado" },
  run_triggered: { icon: "play", color: "var(--status-warning)", label: "Run disparado" },
  query_delta_table: { icon: "table-cells", color: "var(--status-info)", label: "Query executada" },
  query_executed: { icon: "table-cells", color: "var(--status-info)", label: "Query executada" },
  confirmation_required: {
    icon: "exclamation-triangle",
    color: "var(--status-warning)",
    label: "Confirmacao necessaria",
  },
  get_pipeline_status: { icon: "signal", color: "var(--status-success)", label: "Status consultado" },
}

const current = computed(
  () =>
    config[actionType.value] || {
      icon: "bolt",
      color: "var(--text-tertiary)",
      label: actionType.value,
    },
)
const iconName = computed(() => current.value.icon)
const accentColor = computed(() => current.value.color)
const label = computed(() => current.value.label)

const linkUrl = computed(() => {
  const details = props.action.details
  if (!details) return null
  const url = details.url ?? details.pr_url
  return typeof url === "string" ? url : null
})

const linkLabel = computed(() => {
  const details = props.action.details
  if (details?.number) return `#${details.number}`
  return "Ver"
})
</script>
