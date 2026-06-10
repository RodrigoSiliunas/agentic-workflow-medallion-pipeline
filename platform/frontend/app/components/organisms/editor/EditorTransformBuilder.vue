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

    <!-- Seletor de node/tabela alvo — camadas Bronze/Gold visíveis, bloqueadas -->
    <div v-if="nodes.length" class="flex flex-col gap-[4px]">
      <span
        class="text-[10px] font-semibold uppercase tracking-[0.06em]"
        :style="{ color: 'var(--fg-tertiary)' }"
      >
        Tabela alvo
      </span>
      <button
        ref="nodeBtnRef"
        type="button"
        data-testid="node-selector"
        class="flex w-full cursor-pointer items-center gap-[8px] rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--surface-elevated)] px-[10px] py-[7px] text-left font-mono text-[12px] transition-colors duration-100 focus-visible:outline-none focus-visible:shadow-[var(--shadow-focus)]"
        :style="{ color: 'var(--fg-primary)' }"
        @click="toggleNodeMenu"
      >
        <AppIcon name="circle-stack" size="xs" :style="{ color: 'var(--brand-400)', flexShrink: 0 }" />
        <span class="truncate">{{ activeNode?.outputTables[0] || "selecione o node…" }}</span>
        <span
          class="ml-auto rounded-[var(--radius-sm)] px-[6px] py-[1px] text-[10px] font-semibold uppercase"
          :style="{ color: 'var(--brand-400)', background: 'rgba(142,81,246,0.12)', flexShrink: 0 }"
        >
          silver
        </span>
        <AppIcon name="chevron-down" size="xs" :style="{ color: 'var(--fg-tertiary)', flexShrink: 0 }" />
      </button>

      <Teleport to="body">
        <div
          v-if="showNodeMenu"
          ref="nodeMenuRef"
          class="op-floating-menu"
          data-testid="node-selector-menu"
          :style="{ top: `${nodePos.top}px`, left: `${nodePos.left}px`, width: `${nodePos.width}px` }"
        >
          <div class="op-menu-group">Bronze · bloqueada nesta release</div>
          <div class="op-menu-locked">
            <AppIcon name="lock-closed" size="xs" />
            ingestão bronze — gerencie via deploy
          </div>
          <div class="op-menu-group">Silver · editável</div>
          <button
            v-for="node in nodes"
            :key="node.id"
            type="button"
            class="op-menu-item"
            :data-testid="`node-option-${node.id}`"
            @click="pickNode(node.id)"
          >
            <AppIcon
              :name="node.id === activeNode?.id ? 'check-circle' : 'circle-stack'"
              size="xs"
              :style="{ color: 'var(--brand-400)', flexShrink: 0 }"
            />
            <span class="flex min-w-0 flex-col">
              <span class="truncate">{{ node.taskKey }}</span>
              <span class="truncate text-[10px]" :style="{ color: 'var(--fg-tertiary)' }">
                {{ node.outputTables[0] }}
              </span>
            </span>
          </button>
          <div class="op-menu-group">Gold · bloqueada nesta release</div>
          <div class="op-menu-locked">
            <AppIcon name="lock-closed" size="xs" />
            notebooks analíticos — derivados do Silver
          </div>
        </div>
      </Teleport>
    </div>

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
    <div ref="addBtnRef">
      <AppButton
        variant="outline"
        color="neutral"
        size="sm"
        icon="plus"
        block
        @click="toggleAddMenu"
      >
        Adicionar operação
      </AppButton>
    </div>

    <!-- Popover com lista de tipos de operação — teleportado pro body para
         não ser clipado pela barra de tabs/containers com overflow -->
    <Teleport to="body">
      <div
        v-if="showAdd"
        ref="addMenuRef"
        class="op-floating-menu"
        data-testid="add-op-menu"
        :style="{ top: `${addPos.top}px`, left: `${addPos.left}px`, width: `${addPos.width}px` }"
      >
        <div class="op-menu-group">Escolher tipo</div>
        <button
          v-for="opType in OP_TYPES"
          :key="opType.id"
          type="button"
          class="op-menu-item"
          @click="add(opType.id)"
        >
          <AppIcon :name="opType.icon" size="xs" :style="{ color: 'var(--brand-400)', flexShrink: 0 }" />
          {{ opType.label }}
        </button>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import type { TransformDraft, TransformOperation, SourceOfTruth, SchemaColumn } from "~/types/pipeline-editor-v2"
import type { PipelineManifestNode } from "~/types/pipeline-editor"
import { OP_TYPES } from "./constants"

const props = withDefaults(
  defineProps<{
    draft?: TransformDraft | null
    sourceOfTruth?: SourceOfTruth
    autoSavedAt?: string | null
    tableColumns?: SchemaColumn[]
    // Nodes Silver do manifest (alvo selecionável) + node ativo
    nodes?: PipelineManifestNode[]
    selectedNodeId?: string | null
  }>(),
  {
    draft: null,
    sourceOfTruth: null,
    autoSavedAt: null,
    tableColumns: () => [],
    nodes: () => [],
    selectedNodeId: null,
  },
)

const emit = defineEmits<{
  "update:draft": [draft: TransformDraft]
  markActive: []
  selectNode: [nodeId: string]
}>()

const activeNode = computed(
  () => props.nodes.find((n) => n.id === props.selectedNodeId) ?? props.nodes[0] ?? null,
)

// ── Popovers teleportados (não são clipados por containers/tab bar) ───────
const showAdd = ref(false)
const addBtnRef = ref<HTMLElement | null>(null)
const addMenuRef = ref<HTMLElement | null>(null)
const addPos = ref({ top: 0, left: 0, width: 260 })

const showNodeMenu = ref(false)
const nodeBtnRef = ref<HTMLElement | null>(null)
const nodeMenuRef = ref<HTMLElement | null>(null)
const nodePos = ref({ top: 0, left: 0, width: 280 })

onClickOutside(addMenuRef, () => { if (showAdd.value) showAdd.value = false }, { ignore: [addBtnRef] })
onClickOutside(nodeMenuRef, () => { if (showNodeMenu.value) showNodeMenu.value = false }, { ignore: [nodeBtnRef] })

// Posiciona abaixo do anchor; se não couber na viewport, abre pra cima.
function placeMenu(anchor: HTMLElement | null, menu: HTMLElement | null, fallbackH = 280) {
  const r = anchor?.getBoundingClientRect()
  if (!r) return { top: 0, left: 0, width: 260 }
  const menuH = menu?.offsetHeight || fallbackH
  const below = r.bottom + 6
  const top = below + menuH > window.innerHeight ? Math.max(8, r.top - menuH - 6) : below
  return { top, left: r.left, width: Math.max(r.width, 260) }
}

async function toggleAddMenu() {
  showAdd.value = !showAdd.value
  if (showAdd.value) {
    await nextTick()
    addPos.value = placeMenu(addBtnRef.value, addMenuRef.value)
  }
}

async function toggleNodeMenu() {
  showNodeMenu.value = !showNodeMenu.value
  if (showNodeMenu.value) {
    await nextTick()
    nodePos.value = placeMenu(nodeBtnRef.value, nodeMenuRef.value)
  }
}

function pickNode(nodeId: string) {
  emit("selectNode", nodeId)
  showNodeMenu.value = false
}

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

// Emite SEMPRE o draft completo — antes emitia só { operations }, perdendo
// layer/targetNode/targetTable (o autosave salvava um draft inválido).
function emitDraft(newOps: TransformOperation[]) {
  emit("update:draft", {
    layer: "silver",
    targetNode: activeNode.value?.taskKey ?? "",
    targetTable: activeNode.value?.outputTables[0] ?? "",
    ...(props.draft ?? {}),
    operations: newOps,
  } as TransformDraft)
  emit("markActive")
}

// Emite novo rascunho com operação específica atualizada
function update(idx: number, patch: Partial<TransformOperation>) {
  emitDraft(ops.value.map((op, i) => (i === idx ? { ...op, ...patch } : op)))
}

// Remove operação pelo índice
function remove(idx: number) {
  emitDraft(ops.value.filter((_, i) => i !== idx))
}

// Move operação para cima ou para baixo
function move(idx: number, dir: 1 | -1) {
  const newOps = [...ops.value]
  const target = idx + dir
  if (target < 0 || target >= newOps.length) return
  ;[newOps[idx], newOps[target]] = [newOps[target], newOps[idx]]
  emitDraft(newOps)
}

// Adiciona nova operação do tipo escolhido
function add(type: string) {
  const newOp: TransformOperation = { op: type }
  emitDraft([...ops.value, newOp])
  showAdd.value = false
}
</script>

<style>
/* Teleportado pro body — sem scoped, z-index acima de qualquer painel/tab bar */
.op-floating-menu {
  position: fixed;
  z-index: 1000;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-medium);
  overflow: hidden auto;
  max-height: 60vh;
  padding-bottom: 6px;
}

.op-floating-menu .op-menu-group {
  padding: 8px 10px 4px;
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--fg-tertiary);
}

.op-floating-menu .op-menu-item {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  text-align: left;
  font-size: 12px;
  font-family: var(--font-sans);
  color: var(--fg-primary);
  cursor: pointer;
  transition: background-color 100ms;
}

.op-floating-menu .op-menu-item:hover {
  background: var(--surface-elevated);
}

.op-floating-menu .op-menu-locked {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  font-size: 11px;
  color: var(--fg-tertiary);
  cursor: not-allowed;
  opacity: 0.7;
}
</style>
