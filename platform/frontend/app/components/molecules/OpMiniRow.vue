<template>
  <div
    class="flex items-center gap-2 rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--surface-elevated)] px-2 py-1.5 font-sans text-[11px]"
  >
    <!-- Índice numerado -->
    <span
      class="inline-flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full border border-[var(--border)] bg-[var(--surface)] font-mono text-[10px]"
      :style="{ color: 'var(--fg-tertiary)' }"
    >
      {{ index + 1 }}
    </span>

    <!-- Ícone da operação -->
    <AppIcon :name="opMeta.icon" size="xs" :style="{ color: opMeta.color, flexShrink: 0 }" />

    <!-- Nome da op -->
    <span class="font-medium" :style="{ color: 'var(--fg-primary)' }">{{ op.op }}</span>

    <!-- Resumo inline da operação -->
    <span class="inline-flex items-center gap-1" :style="{ color: 'var(--fg-secondary)' }">
      <template v-if="op.op === 'drop_column'">
        <AppCode>{{ op.column }}</AppCode>
      </template>
      <template v-else-if="op.op === 'rename_column'">
        <AppCode>{{ op.column }}</AppCode>
        <span :style="{ color: 'var(--fg-tertiary)' }">→</span>
        <AppCode>{{ op.newName }}</AppCode>
      </template>
      <template v-else-if="op.op === 'cast_column'">
        <AppCode>{{ op.column }}</AppCode>
        <span :style="{ color: 'var(--fg-tertiary)' }">as</span>
        <AppCode>{{ op.dataType }}</AppCode>
      </template>
      <template v-else-if="op.op === 'trim'">
        <AppCode>{{ op.column }}</AppCode>
      </template>
      <template v-else-if="op.op === 'regex_replace'">
        <AppCode>{{ op.column }}</AppCode>
        <span :style="{ color: 'var(--fg-tertiary)' }">/{{ op.pattern }}/</span>
      </template>
      <template v-else-if="op.op === 'coalesce'">
        <AppCode>{{ op.column }}</AppCode>
      </template>
      <template v-else-if="op.op === 'derive_column'">
        <AppCode>{{ op.column }}</AppCode>
        <span :style="{ color: 'var(--fg-tertiary)' }">=</span>
        <AppCode>{{ op.expression }}</AppCode>
      </template>
      <template v-else-if="op.op === 'filter_rows'">
        <AppCode>{{ op.expression }}</AppCode>
      </template>
      <template v-else-if="op.op === 'date_format'">
        <AppCode>{{ op.column }}</AppCode>
        <span :style="{ color: 'var(--fg-tertiary)' }">{{ op.format }}</span>
      </template>
      <template v-else-if="op.op === 'json_extract'">
        <AppCode>{{ op.column }}</AppCode>
        <span :style="{ color: 'var(--fg-tertiary)' }">↦</span>
        <AppCode>{{ op.newName }}</AppCode>
      </template>
      <template v-else-if="op.op === 'mask_pii'">
        <AppCode>{{ op.column }}</AppCode>
      </template>
    </span>
  </div>
</template>

<script setup lang="ts">
import type { TransformOperation } from "~/types/pipeline-editor"

const props = defineProps<{
  op: TransformOperation
  index: number
}>()

// Mapa op → ícone + cor (port fiel do protótipo f1e5f9ab)
const OP_ICON: Record<string, { icon: string; color: string }> = {
  drop_column:   { icon: "minus-circle",      color: "var(--status-error)" },
  rename_column: { icon: "arrows-right-left", color: "var(--status-info)" },
  cast_column:   { icon: "arrow-path",        color: "var(--brand-400)" },
  trim:          { icon: "scissors",          color: "var(--fg-secondary)" },
  regex_replace: { icon: "magnifying-glass",  color: "var(--brand-400)" },
  coalesce:      { icon: "rectangle-stack",   color: "var(--brand-400)" },
  derive_column: { icon: "plus-circle",       color: "var(--status-success)" },
  filter_rows:   { icon: "funnel",            color: "var(--status-warning)" },
  date_format:   { icon: "calendar",          color: "var(--brand-400)" },
  json_extract:  { icon: "code-bracket",      color: "var(--brand-400)" },
  mask_pii:      { icon: "eye-slash",         color: "var(--status-warning)" },
}

const opMeta = computed(
  () => OP_ICON[props.op.op] ?? { icon: "bolt", color: "var(--fg-tertiary)" },
)
</script>
