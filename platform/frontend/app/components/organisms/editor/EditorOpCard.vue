<template>
  <div
    class="overflow-hidden rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)]"
  >
    <!-- Cabeçalho do card -->
    <div
      class="flex items-center gap-[8px] border-b border-[var(--border)] px-[10px] py-[8px]"
      :style="{ background: 'var(--surface-elevated)' }"
    >
      <!-- Índice com cursor grab -->
      <span
        class="inline-flex h-[20px] w-[20px] flex-shrink-0 cursor-grab items-center justify-center rounded-full border border-[var(--border)] font-mono text-[10px] font-semibold select-none"
        :style="{ color: 'var(--fg-tertiary)' }"
      >
        {{ index + 1 }}
      </span>

      <!-- Ícone do tipo de operação -->
      <AppIcon
        v-if="opMeta"
        :name="opMeta.icon"
        size="xs"
        :style="{ color: opMeta.color, flexShrink: 0 }"
      />

      <!-- Dropdown de tipo (botão estilizado) -->
      <div class="relative flex-1 min-w-0">
        <button
          ref="typeBtnRef"
          type="button"
          class="flex h-[24px] items-center gap-[5px] rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--surface)] px-[8px] font-sans text-[11px] font-semibold transition-colors duration-100 hover:bg-[var(--surface-elevated)] focus-visible:outline-none focus-visible:shadow-[var(--shadow-focus)]"
          :style="{ color: 'var(--fg-primary)', cursor: 'pointer' }"
          @click="toggleTypeDropdown"
        >
          {{ currentOpType?.label ?? op.op }}
          <AppIcon name="chevron-down" size="xs" :style="{ color: 'var(--fg-tertiary)' }" />
        </button>

        <!-- Dropdown de tipos de operação (posicionado inline) -->
        <div
          v-if="typeDropdownOpen"
          ref="typeMenuRef"
          class="op-type-dropdown"
        >
          <button
            v-for="opType in OP_TYPES"
            :key="opType.id"
            type="button"
            class="flex w-full items-center gap-[8px] rounded-[var(--radius-sm)] border-none px-[8px] py-[7px] text-left text-[12px] transition-colors duration-100 hover:bg-[var(--surface-elevated)]"
            :class="opType.id === op.op ? 'bg-[var(--surface-elevated)]' : 'bg-transparent'"
            :style="{ color: 'var(--fg-primary)', fontFamily: 'var(--font-sans)', cursor: 'pointer' }"
            @click="selectOpType(opType.id)"
          >
            <AppIcon
              :name="OP_ICON[opType.id]?.icon ?? 'squares-plus'"
              size="xs"
              :style="{ color: OP_ICON[opType.id]?.color ?? 'var(--brand-400)', flexShrink: 0 }"
            />
            {{ opType.label }}
            <AppIcon
              v-if="opType.id === op.op"
              name="check"
              size="xs"
              :style="{ color: 'var(--brand-400)', marginLeft: 'auto' }"
            />
          </button>
        </div>
      </div>

      <!-- Código da operação -->
      <AppCode class="flex-shrink-0 text-[10px]">{{ op.op }}</AppCode>

      <!-- Ações: mover cima, mover baixo, remover -->
      <div class="ml-auto flex items-center gap-[2px]">
        <AppIconBtn
          icon="chevron-up"
          label="Mover para cima"
          :size="24"
          :disabled="index === 0"
          @click="emit('move', { index, dir: -1 })"
        />
        <AppIconBtn
          icon="chevron-down"
          label="Mover para baixo"
          :size="24"
          :disabled="index === total - 1"
          @click="emit('move', { index, dir: 1 })"
        />
        <AppIconBtn
          icon="x-mark"
          label="Remover operação"
          :size="24"
          @click="emit('remove', index)"
        />
      </div>
    </div>

    <!-- Campos de configuração da operação -->
    <div
      v-if="fields.length > 0"
      class="p-[10px]"
      :style="{ display: 'grid', gap: '10px', gridTemplateColumns: fields.length > 1 ? '1fr 1fr' : '1fr' }"
    >
      <div
        v-for="field in fields"
        :key="field.key"
        class="flex flex-col gap-[4px]"
        :style="field.kind === 'multi_columns' ? { gridColumn: '1 / -1' } : {}"
      >
        <!-- Label do campo -->
        <span
          class="text-[10px] font-semibold uppercase tracking-[0.06em]"
          :style="{ color: 'var(--fg-tertiary)' }"
        >
          {{ fieldLabel(field.key) }}
        </span>

        <!-- ColumnPicker para colunas existentes -->
        <ColumnPicker
          v-if="field.kind === 'existing_column'"
          :model-value="getFieldString(field.key)"
          :columns="tableColumns"
          :placeholder="field.placeholder ?? 'Selecione coluna…'"
          @update:model-value="emit('change', { [field.key]: $event })"
        />

        <!-- ColumnPicker com criação livre para novas colunas -->
        <ColumnPicker
          v-else-if="field.kind === 'new_column'"
          :model-value="getFieldString(field.key)"
          :columns="tableColumns"
          :placeholder="field.placeholder ?? 'Nome da nova coluna…'"
          :allow-create="true"
          @update:model-value="emit('change', { [field.key]: $event })"
        />

        <!-- MultiColumnPicker para seleção múltipla -->
        <MultiColumnPicker
          v-else-if="field.kind === 'multi_columns'"
          :model-value="getFieldStringArray(field.key)"
          :columns="tableColumns"
          @update:model-value="emit('change', { [field.key]: $event })"
        />

        <!-- DataTypePicker para seleção de tipo Spark -->
        <DataTypePicker
          v-else-if="field.kind === 'data_type'"
          :model-value="getFieldString(field.key)"
          :options="SPARK_DATA_TYPES"
          @update:model-value="emit('change', { [field.key]: $event })"
        />

        <!-- AppInput para texto livre -->
        <AppInput
          v-else
          :model-value="getFieldString(field.key)"
          :placeholder="field.placeholder ?? ''"
          size="sm"
          :style="field.mono ? { fontFamily: 'var(--font-mono)', fontSize: '12px' } : {}"
          @update:model-value="emit('change', { [field.key]: $event })"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onClickOutside } from "@vueuse/core"
import type { TransformOperation, SchemaColumn } from "~/types/pipeline-editor-v2"
import { OP_TYPES, OP_ICON, SPARK_DATA_TYPES } from "./constants"

const props = withDefaults(
  defineProps<{
    op: TransformOperation
    index: number
    total: number
    tableColumns?: SchemaColumn[]
  }>(),
  {
    tableColumns: () => [],
  },
)

const emit = defineEmits<{
  change: [patch: Partial<TransformOperation>]
  remove: [index: number]
  move: [payload: { index: number; dir: 1 | -1 }]
}>()

// Referências para o dropdown de tipo de operação
const typeDropdownOpen = ref(false)
const typeBtnRef = ref<HTMLElement | null>(null)
const typeMenuRef = ref<HTMLElement | null>(null)

// Fecha dropdown ao clicar fora
onClickOutside(typeMenuRef, () => {
  if (typeDropdownOpen.value) typeDropdownOpen.value = false
}, { ignore: [typeBtnRef] })

function toggleTypeDropdown() {
  typeDropdownOpen.value = !typeDropdownOpen.value
}

function selectOpType(newType: string) {
  // Ao trocar de tipo, mantém apenas o campo op
  emit("change", {
    op: newType,
    column: undefined,
    new_name: undefined,
    data_type: undefined,
    expression: undefined,
    pattern: undefined,
    replacement: undefined,
    source_columns: undefined,
    format: undefined,
    json_path: undefined,
  })
  typeDropdownOpen.value = false
}

// Metadados do tipo atual
const opMeta = computed(() => OP_ICON[props.op.op])
const currentOpType = computed(() => OP_TYPES.find((t) => t.id === props.op.op))

// Configuração de campos por tipo de operação
interface FieldConfig {
  key: string
  kind?: "existing_column" | "new_column" | "multi_columns" | "data_type" | "text"
  placeholder?: string
  mono?: boolean
}

function fieldsFor(type: string): FieldConfig[] {
  switch (type) {
    case "drop_column":
      return [{ key: "column", kind: "existing_column" }]
    case "rename_column":
      return [
        { key: "column", kind: "existing_column" },
        { key: "new_name", kind: "text", placeholder: "ex: customer_id" },
      ]
    case "cast_column":
      return [
        { key: "column", kind: "existing_column" },
        { key: "data_type", kind: "data_type" },
      ]
    case "trim":
      return [{ key: "column", kind: "existing_column" }]
    case "regex_replace":
      return [
        { key: "column" },
        { key: "pattern", kind: "text", mono: true },
        { key: "replacement", kind: "text" },
      ]
    case "coalesce":
      return [
        { key: "column", kind: "new_column" },
        { key: "source_columns", kind: "multi_columns" },
      ]
    case "derive_column":
      return [
        { key: "column", kind: "text" },
        { key: "expression", kind: "text", mono: true },
      ]
    case "filter_rows":
      return [{ key: "expression", kind: "text", mono: true }]
    case "date_format":
      return [
        { key: "column" },
        { key: "format", kind: "text", mono: true },
      ]
    case "json_extract":
      return [
        { key: "column" },
        { key: "json_path", kind: "text", mono: true },
        { key: "new_name", kind: "text" },
      ]
    case "mask_pii":
      return [{ key: "column", kind: "existing_column" }]
    default:
      return []
  }
}

const fields = computed(() => fieldsFor(props.op.op))

// Helpers para acessar campos da operação com tipo seguro sem usar cast no template
function getFieldString(key: string): string | undefined {
  return (props.op as Record<string, unknown>)[key] as string | undefined
}

function getFieldStringArray(key: string): string[] {
  return ((props.op as Record<string, unknown>)[key] as string[] | undefined) ?? []
}

// Gera label legível para o campo
function fieldLabel(key: string): string {
  const labels: Record<string, string> = {
    column: "Coluna",
    new_name: "Novo nome",
    data_type: "Tipo",
    expression: "Expressão",
    pattern: "Padrão (regex)",
    replacement: "Substituição",
    source_columns: "Colunas de origem",
    format: "Formato",
    json_path: "JSON path",
  }
  return labels[key] ?? key
}
</script>

<style scoped>
.op-type-dropdown {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  z-index: 100;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-medium);
  min-width: 220px;
  max-height: 300px;
  overflow-y: auto;
  padding: 4px;
}
</style>
