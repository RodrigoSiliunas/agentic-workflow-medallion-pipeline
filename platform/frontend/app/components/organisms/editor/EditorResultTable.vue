<template>
  <div class="flex flex-col gap-[8px]">
    <!-- Cabeçalho com pill e contagem de linhas -->
    <div class="flex items-center justify-between gap-[8px]">
      <AppPill :tone="tone" :dot="true" size="xs">{{ label }}</AppPill>
      <span class="font-mono text-[11px]" :style="{ color: 'var(--fg-tertiary)' }">
        {{ rows.length }} de 50 linhas exibidas
      </span>
    </div>

    <!-- Tabela com overflow e maxHeight opcional -->
    <div
      class="overflow-x-auto rounded-[var(--radius-md)] border border-[var(--border)]"
      :style="maxHeight ? { maxHeight, overflowY: 'auto' } : {}"
    >
      <table
        class="w-full border-collapse text-left"
        style="font-family: var(--font-mono); font-size: 12px"
      >
        <thead>
          <tr>
            <th
              v-for="col in cols"
              :key="col"
              class="sticky top-0 whitespace-nowrap border-b border-[var(--border)] px-[10px] py-[7px] text-[11px] font-semibold"
              :style="headerStyle(col)"
            >
              <span class="inline-flex items-center gap-[5px]">
                <!-- Ícone indicando estado da coluna -->
                <AppIcon
                  v-if="removedSet.has(col)"
                  name="minus-circle"
                  size="xs"
                  :style="{ color: 'var(--status-error)' }"
                />
                <AppIcon
                  v-else-if="renamedFromSet.has(col) || renamedToSet.has(col)"
                  name="arrows-right-left"
                  size="xs"
                  :style="{ color: 'var(--status-info)' }"
                />
                <AppIcon
                  v-else-if="derivedSet.has(col)"
                  name="plus-circle"
                  size="xs"
                  :style="{ color: 'var(--status-success)' }"
                />
                {{ col }}
              </span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(row, ri) in rows"
            :key="ri"
            class="border-b border-[var(--border)] last:border-b-0"
          >
            <td
              v-for="col in cols"
              :key="col"
              class="whitespace-nowrap px-[10px] py-[6px]"
              :style="cellStyle(col, row[col])"
            >
              <span v-if="row[col] === null || row[col] === undefined" :style="{ color: 'var(--fg-tertiary)' }">
                —
              </span>
              <span v-else>{{ row[col] }}</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { SchemaDelta } from "~/types/pipeline-editor-v2"

const props = withDefaults(
  defineProps<{
    rows?: Record<string, unknown>[]
    schemaDelta?: SchemaDelta | null
    label?: "Depois" | "Antes"
    tone?: "success" | "neutral"
    maxHeight?: string | null
  }>(),
  {
    rows: () => [],
    schemaDelta: null,
    label: "Depois",
    tone: "success",
    maxHeight: null,
  },
)

// Colunas derivadas das chaves da primeira linha
const cols = computed(() => (props.rows[0] ? Object.keys(props.rows[0]) : []))

// Conjuntos para lookup rápido de estado de coluna
const removedSet = computed(() => new Set(props.schemaDelta?.removed ?? []))

const renamedFromSet = computed(
  () => new Set((props.schemaDelta?.renamed ?? []).map((r) => r.from)),
)

const renamedToSet = computed(
  () => new Set((props.schemaDelta?.renamed ?? []).map((r) => r.to)),
)

const derivedSet = computed(() => {
  const items = props.schemaDelta?.derived ?? []
  return new Set(
    items.map((d) => (typeof d === "string" ? d : d.name)),
  )
})

function headerStyle(col: string) {
  if (removedSet.value.has(col)) {
    return {
      color: "var(--status-error)",
      background: "rgba(239,68,68,0.06)",
    }
  }
  if (renamedFromSet.value.has(col) || renamedToSet.value.has(col)) {
    return {
      color: "var(--status-info)",
      background: "rgba(59,130,246,0.06)",
    }
  }
  if (derivedSet.value.has(col)) {
    return {
      color: "var(--status-success)",
      background: "rgba(34,197,94,0.06)",
    }
  }
  return { color: "var(--fg-secondary)", background: "var(--surface-elevated)" }
}

function cellStyle(col: string, value: unknown) {
  if (removedSet.value.has(col)) {
    return {
      color: "var(--status-error)",
      textDecoration: "line-through",
      opacity: "0.7",
    }
  }
  if (derivedSet.value.has(col)) {
    return { color: "var(--status-success)" }
  }
  if (value === null || value === undefined) {
    return { color: "var(--fg-tertiary)" }
  }
  return { color: "var(--fg-secondary)" }
}
</script>
