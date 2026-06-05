<template>
  <div
    class="flex gap-[10px] rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--surface)] p-[10px_12px]"
    :style="{ borderLeft: `3px solid ${stepMeta.color}` }"
  >
    <!-- Índice numerado -->
    <span
      class="inline-flex h-[22px] w-[22px] flex-shrink-0 items-center justify-center rounded-full border border-[var(--border)] bg-[var(--surface-elevated)] font-mono text-[11px] font-semibold"
      :style="{ color: 'var(--fg-secondary)' }"
    >
      {{ index + 1 }}
    </span>

    <div class="flex min-w-0 flex-1 flex-col gap-1">
      <!-- Cabeçalho: ícone + label do tipo + nota opcional -->
      <div class="flex flex-wrap items-center gap-1.5">
        <AppIcon :name="stepMeta.icon" size="xs" :style="{ color: stepMeta.color }" />
        <span
          class="text-[11px] font-semibold uppercase tracking-[0.04em]"
          :style="{ color: stepMeta.color }"
        >
          {{ stepMeta.label }}
        </span>
        <span v-if="note" class="text-[11px]" :style="{ color: 'var(--fg-tertiary)' }">· {{ note }}</span>
      </div>

      <!-- Conteúdo do passo: colunas, expressões, etc. -->
      <div
        class="flex flex-wrap items-center gap-1.5 text-[12px]"
        :style="{ color: 'var(--fg-primary)' }"
      >
        <!-- Renomear: from → to -->
        <template v-if="kind === 'renamed' && fromColumn && toColumn">
          <AppCode>{{ fromColumn }}</AppCode>
          <span :style="{ color: 'var(--fg-tertiary)' }">→</span>
          <AppCode>{{ toColumn }}</AppCode>
        </template>

        <!-- Derivada: column = expression -->
        <template v-else-if="kind === 'derived' && expression">
          <AppCode>{{ column }}</AppCode>
          <span :style="{ color: 'var(--fg-tertiary)' }">=</span>
          <AppCode>{{ expression }}</AppCode>
        </template>

        <!-- Cast: column as tipo -->
        <template v-else-if="kind === 'cast' && castType">
          <AppCode>{{ column }}</AppCode>
          <span :style="{ color: 'var(--fg-tertiary)' }">as</span>
          <AppCode>{{ castType }}</AppCode>
        </template>

        <!-- Filtro/padrão: expressão ou coluna + params -->
        <template v-else>
          <AppCode v-if="column">{{ column }}</AppCode>
          <span v-if="params" :style="{ color: 'var(--fg-tertiary)' }">{{ params }}</span>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
export type TransformStepKind = "removed" | "renamed" | "modified" | "derived" | "filter" | "cast"

const props = defineProps<{
  index: number
  kind: TransformStepKind
  column?: string
  fromColumn?: string
  toColumn?: string
  expression?: string
  castType?: string
  params?: string
  note?: string
}>()

const KIND_MAP: Record<TransformStepKind, { icon: string; color: string; label: string }> = {
  removed:  { icon: "minus-circle",      color: "var(--status-error)",   label: "Coluna removida" },
  renamed:  { icon: "arrows-right-left", color: "var(--status-info)",    label: "Coluna renomeada" },
  derived:  { icon: "plus-circle",       color: "var(--status-success)", label: "Coluna derivada" },
  modified: { icon: "pencil-square",     color: "var(--brand-400)",      label: "Coluna modificada" },
  filter:   { icon: "funnel",            color: "var(--status-warning)", label: "Filtro de linhas" },
  cast:     { icon: "arrow-path",        color: "var(--brand-400)",      label: "Cast de tipo" },
}

const stepMeta = computed(() => KIND_MAP[props.kind] ?? KIND_MAP.modified)
</script>
