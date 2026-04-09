<template>
  <div
    class="flex items-center gap-2 px-3 py-2 rounded-lg text-xs"
    :style="{
      background: 'var(--bg-elevated)',
      border: '1px solid var(--border-subtle)',
      borderLeft: `3px solid ${accentColor}`,
    }"
  >
    <UIcon :name="icon" :style="{ color: accentColor }" />
    <span class="flex-1" style="color: var(--text-secondary)">{{ label }}</span>
    <a
      v-if="action.details?.pr_url"
      :href="action.details.pr_url"
      target="_blank"
      class="underline"
      style="color: var(--brand-primary)"
    >
      Ver PR
    </a>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  action: { type?: string; action?: string; status?: string; details?: Record<string, any> }
}>()

const actionType = computed(() => props.action.action || props.action.type || "unknown")

const config: Record<string, { icon: string; color: string; label: string }> = {
  create_pull_request: { icon: "i-heroicons-code-bracket", color: "var(--brand-primary)", label: "PR criado" },
  pr_created: { icon: "i-heroicons-code-bracket", color: "var(--brand-primary)", label: "PR criado" },
  trigger_pipeline_run: { icon: "i-heroicons-play", color: "var(--status-warning)", label: "Run disparado" },
  run_triggered: { icon: "i-heroicons-play", color: "var(--status-warning)", label: "Run disparado" },
  query_delta_table: { icon: "i-heroicons-table-cells", color: "var(--status-info)", label: "Query executada" },
  query_executed: { icon: "i-heroicons-table-cells", color: "var(--status-info)", label: "Query executada" },
  confirmation_required: { icon: "i-heroicons-exclamation-triangle", color: "var(--status-warning)", label: "Confirmação necessária" },
  get_pipeline_status: { icon: "i-heroicons-signal", color: "var(--status-success)", label: "Status consultado" },
}

const current = computed(() => config[actionType.value] || { icon: "i-heroicons-bolt", color: "var(--text-tertiary)", label: actionType.value })
const icon = computed(() => current.value.icon)
const accentColor = computed(() => current.value.color)
const label = computed(() => current.value.label)
</script>
