<template>
  <div
    class="flex min-h-[30px] flex-wrap items-center gap-1 rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--surface-elevated)] p-[4px_6px]"
  >
    <!-- Chips das colunas selecionadas -->
    <span
      v-for="name in selectedList"
      :key="name"
      class="inline-flex items-center gap-1 rounded-full border border-[var(--border)] bg-[var(--surface)] px-[7px] py-[2px] font-mono text-[11px]"
      :style="{ color: 'var(--fg-primary)' }"
    >
      {{ name }}
      <span
        v-if="colMap[name]"
        class="text-[10px]"
        :style="{ color: 'var(--fg-tertiary)' }"
      >
        ·{{ colMap[name].type }}
      </span>
      <button
        type="button"
        class="inline-flex h-4 w-4 cursor-pointer items-center justify-center rounded-full border-none bg-transparent"
        :style="{ color: 'var(--fg-tertiary)' }"
        :aria-label="`Remover ${name}`"
        @click="remove(name)"
      >
        <AppIcon name="x-mark" size="xs" />
      </button>
    </span>

    <!-- Picker de coluna adicional -->
    <div class="min-w-[140px] flex-1">
      <ColumnPicker
        :columns="remainingColumns"
        :placeholder="placeholder"
        @update:model-value="add"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { SchemaColumn } from "~/types/pipeline-editor-v2"

const props = withDefaults(
  defineProps<{
    modelValue?: string | string[]
    columns?: SchemaColumn[]
    placeholder?: string
  }>(),
  {
    modelValue: () => [],
    columns: () => [],
    placeholder: "Adicionar coluna…",
  },
)

const emit = defineEmits<{
  "update:modelValue": [value: string[]]
}>()

const selectedList = computed<string[]>(() => {
  if (Array.isArray(props.modelValue)) return props.modelValue
  if (typeof props.modelValue === "string" && props.modelValue) {
    return props.modelValue
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean)
  }
  return []
})

// Mapa rápido nome → coluna
const colMap = computed(() =>
  Object.fromEntries(props.columns.map((c) => [c.name, c])),
)

// Colunas ainda não selecionadas
const remainingColumns = computed(() =>
  props.columns.filter((c) => !selectedList.value.includes(c.name)),
)

function remove(name: string) {
  emit(
    "update:modelValue",
    selectedList.value.filter((x) => x !== name),
  )
}

function add(name: string) {
  if (!name || selectedList.value.includes(name)) return
  emit("update:modelValue", [...selectedList.value, name])
}
</script>
