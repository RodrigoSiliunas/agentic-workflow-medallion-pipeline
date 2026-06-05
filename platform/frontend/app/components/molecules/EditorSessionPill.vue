<template>
  <span class="inline-flex items-center gap-1.5">
    <!-- ID da sessão em monospace -->
    <span
      class="inline-flex items-center gap-1.5 rounded-full px-[9px] py-[3px] font-mono text-[11px]"
      :style="{ background: 'var(--surface-elevated)', border: '1px solid var(--border)', color: 'var(--fg-secondary)' }"
    >
      <AppIcon name="hashtag" size="xs" :style="{ color: 'var(--fg-tertiary)' }" />
      {{ id }}
    </span>
    <!-- Status pill -->
    <AppPill :tone="statusMeta.tone" dot size="xs">{{ statusMeta.label }}</AppPill>
  </span>
</template>

<script setup lang="ts">
import type { SessionStatusV2 } from "~/types/pipeline-editor-v2"

const props = withDefaults(
  defineProps<{
    id: string
    status?: SessionStatusV2
  }>(),
  { status: "draft" },
)

const STATUS_MAP: Record<
  SessionStatusV2,
  { tone: "warning" | "info" | "success" | "error"; label: string }
> = {
  draft:             { tone: "warning", label: "Rascunho" },
  preview_ok:        { tone: "info",    label: "Preview OK" },
  pr_created:        { tone: "success", label: "PR aberto" },
  validated:         { tone: "success", label: "Validado" },
  validation_failed: { tone: "error",   label: "Validação falhou" },
}

const statusMeta = computed(() => STATUS_MAP[props.status] ?? STATUS_MAP.draft)
</script>
