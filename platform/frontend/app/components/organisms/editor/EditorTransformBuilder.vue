<template>
  <div
    class="relative flex h-full flex-col overflow-auto"
    style="padding: 14px 14px 32px; gap: 10px"
    :style="sourceRingStyle"
  >
    <!-- Badge indicando fonte da verdade quando é o builder -->
    <div
      v-if="sourceOfTruth === 'builder'"
      class="flex items-center gap-[6px] rounded-[var(--radius-md)] border px-[10px] py-[6px]"
      style="border-color: rgba(142,81,246,0.35); background: rgba(142,81,246,0.06)"
    >
      <AppStatusDot tone="brand" :pulse="true" :size="6" />
      <span class="text-[11px] font-semibold" :style="{ color: 'var(--brand-400)' }">
        Fonte da verdade · builder
      </span>
    </div>

    <!-- Cabeçalho da seção -->
    <SectionHeader
      overline="Builder · low-code"
      :title="`${ops.length} operaç${ops.length !== 1 ? 'ões' : 'ão'}`"
    >
      <template #action>
        <span
          v-if="autoSavedAt"
          class="font-mono text-[10px]"
          :style="{ color: 'var(--fg-tertiary)' }"
        >
          salvo {{ autoSavedAt }}
        </span>
      </template>
    </SectionHeader>

    <!-- Estado vazio -->
    <div
      v-if="ops.length === 0"
      class="flex flex-col items-center justify-center gap-[8px] rounded-[var(--radius-lg)] border border-dashed border-[var(--border)] bg-[var(--surface)] py-[24px] text-center"
      :style="{ color: 'var(--fg-tertiary)' }"
    >
      <AppIcon name="squares-plus" size="lg" :style="{ color: 'var(--fg-tertiary)' }" />
      <p class="text-[12px]">
        Nenhuma operação ainda. Use chat NL para gerar ou adicione abaixo.
      </p>
    </div>

    <!-- Lista de operações -->
    <EditorOpCard
      v-for="(op, i) in ops"
      :key="i"
      :op="op"
      :index="i"
      :total="ops.length"
      :table-columns="tableColumns"
      @change="update(i, $event)"
      @remove="remove($event)"
      @move="move($event.index, $event.dir)"
    />

    <!-- Botão de adicionar nova operação -->
    <div class="relative">
      <AppButton
        variant="outline"
        color="neutral"
        size="sm"
        icon="plus"
        block
        @click="showAdd = !showAdd"
      >
        Adicionar operação
      </AppButton>

      <!-- Popover com lista de tipos de operação -->
      <div
        v-if="showAdd"
        class="op-add-popover"
      >
        <div
          class="text-[10px] font-semibold uppercase tracking-[0.06em] px-[10px] pt-[8px] pb-[4px]"
          :style="{ color: 'var(--fg-tertiary)' }"
        >
          Escolher tipo
        </div>
        <button
          v-for="opType in OP_TYPES"
          :key="opType.id"
          type="button"
          class="flex w-full items-center gap-[8px] rounded-[var(--radius-sm)] border-none px-[10px] py-[8px] text-left text-[12px] transition-colors duration-100 hover:bg-[var(--surface-elevated)]"
          :style="{ color: 'var(--fg-primary)', fontFamily: 'var(--font-sans)', background: 'transparent', cursor: 'pointer' }"
          @click="add(opType.id)"
        >
          <AppIcon :name="opType.icon" size="xs" :style="{ color: 'var(--brand-400)', flexShrink: 0 }" />
          {{ opType.label }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { TransformDraft, TransformOperation, SourceOfTruth, SchemaColumn } from "~/types/pipeline-editor-v2"
import { OP_TYPES } from "./constants"

const props = withDefaults(
  defineProps<{
    draft?: TransformDraft | null
    sourceOfTruth?: SourceOfTruth
    autoSavedAt?: string | null
    tableColumns?: SchemaColumn[]
  }>(),
  {
    draft: null,
    sourceOfTruth: null,
    autoSavedAt: null,
    tableColumns: () => [],
  },
)

const emit = defineEmits<{
  "update:draft": [draft: TransformDraft]
  markActive: []
}>()

const showAdd = ref(false)

// Operações atuais
const ops = computed<TransformOperation[]>(() => props.draft?.operations ?? [])

// Anel visual quando builder é a fonte da verdade
const sourceRingStyle = computed(() => {
  if (props.sourceOfTruth === "builder") {
    return {
      outline: "1px solid rgba(142,81,246,0.25)",
      background: "rgba(142,81,246,0.025)",
    }
  }
  return {}
})

// Emite novo rascunho com operação específica atualizada
function update(idx: number, patch: Partial<TransformOperation>) {
  const newOps = ops.value.map((op, i) => (i === idx ? { ...op, ...patch } : op))
  emit("update:draft", { operations: newOps })
  emit("markActive")
}

// Remove operação pelo índice
function remove(idx: number) {
  const newOps = ops.value.filter((_, i) => i !== idx)
  emit("update:draft", { operations: newOps })
  emit("markActive")
}

// Move operação para cima ou para baixo
function move(idx: number, dir: 1 | -1) {
  const newOps = [...ops.value]
  const target = idx + dir
  if (target < 0 || target >= newOps.length) return
  ;[newOps[idx], newOps[target]] = [newOps[target], newOps[idx]]
  emit("update:draft", { operations: newOps })
  emit("markActive")
}

// Adiciona nova operação do tipo escolhido
function add(type: string) {
  const newOp: TransformOperation = { op: type }
  emit("update:draft", { operations: [...ops.value, newOp] })
  emit("markActive")
  showAdd.value = false
}
</script>

<style scoped>
.op-add-popover {
  position: absolute;
  bottom: calc(100% + 6px);
  left: 0;
  right: 0;
  z-index: 50;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-medium);
  overflow: hidden;
  padding-bottom: 6px;
}
</style>
