<template>
  <div
    class="grid items-center"
    style="grid-template-columns: 1.6fr 1.2fr 0.7fr 1.3fr"
    :style="[
      { padding: dense ? '6px 12px' : '8px 12px', opacity: isRemoved ? '0.55' : '1' },
      borderTop ? { borderTop: '1px solid var(--border)' } : {},
    ]"
  >
    <!-- Coluna: nome (com from se renomeada) -->
    <span class="inline-flex min-w-0 items-center gap-1.5">
      <template v-if="column.state === 'renamed' && column.from">
        <span class="inline-flex items-center gap-1">
          <AppCode class="line-through" :style="{ color: 'var(--fg-tertiary)', borderColor: 'var(--border)' }">
            {{ column.from }}
          </AppCode>
          <AppIcon name="arrow-right" size="xs" :style="{ color: 'var(--fg-tertiary)' }" />
        </span>
      </template>
      <AppCode :style="{ textDecoration: isRemoved ? 'line-through' : 'none' }">
        {{ column.name }}
      </AppCode>
    </span>

    <!-- Tipo -->
    <span class="font-mono text-[11px]" :style="{ color: 'var(--fg-secondary)' }">
      {{ column.type }}
    </span>

    <!-- Nullable -->
    <span class="font-mono text-[11px]" :style="{ color: 'var(--fg-tertiary)' }">
      {{ nullableLabel }}
    </span>

    <!-- Estado -->
    <span class="inline-flex items-center gap-1.5">
      <AppPill :tone="stateMeta.tone" dot size="xs">{{ stateMeta.label }}</AppPill>
      <span v-if="column.note" class="text-[11px]" :style="{ color: 'var(--fg-tertiary)' }">
        {{ column.note }}
      </span>
    </span>
  </div>
</template>

<script setup lang="ts">
import type { SchemaColumn } from "~/types/pipeline-editor-v2"

const props = withDefaults(
  defineProps<{
    column: SchemaColumn
    dense?: boolean
    borderTop?: boolean
  }>(),
  {
    dense: false,
    borderTop: false,
  },
)

const isRemoved = computed(() => props.column.state === "removed")

const nullableLabel = computed(() => {
  if (props.column.nullable === false) return "NOT NULL"
  if (props.column.nullable === true) return "yes"
  return "—"
})

const STATE_META: Record<string, { tone: "neutral" | "success" | "warning" | "info" | "brand" | "error"; label: string }> = {
  renamed:   { tone: "info",    label: "Renomeada" },
  derived:   { tone: "success", label: "Derivada" },
  modified:  { tone: "brand",   label: "Modificada" },
  added:     { tone: "success", label: "Adicionada" },
  removed:   { tone: "error",   label: "Removida" },
  unchanged: { tone: "neutral", label: "Sem mudança" },
}

const stateMeta = computed(() => {
  const s = props.column.state ?? "unchanged"
  return STATE_META[s] ?? STATE_META.unchanged
})
</script>
