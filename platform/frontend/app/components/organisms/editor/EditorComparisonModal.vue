<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="comp-backdrop"
      @click="emit('close')"
    >
      <div class="comp-modal" @click.stop>
        <!-- Cabeçalho -->
        <header class="comp-header">
          <div class="flex items-center gap-[10px]">
            <div
              class="flex h-[30px] w-[30px] flex-shrink-0 items-center justify-center rounded-[var(--radius-md)]"
              style="background: rgba(142, 81, 246, 0.12)"
            >
              <AppIcon name="squares-2x2" size="sm" :style="{ color: 'var(--brand-400)' }" />
            </div>
            <div class="flex flex-col gap-[1px]">
              <h3 class="comp-title">Comparar antes / depois</h3>
              <span class="font-mono text-[10px]" :style="{ color: 'var(--fg-tertiary)' }">
                preview namespace
              </span>
            </div>
          </div>
          <AppIconBtn icon="x-mark" label="Fechar comparação" :size="28" @click="emit('close')" />
        </header>

        <!-- Faixa de estatísticas -->
        <div
          class="flex flex-wrap items-center gap-[8px] border-b border-[var(--border)] px-[18px] py-[10px]"
          :style="{ background: 'var(--surface-elevated)' }"
        >
          <AppPill v-if="removedCols.size > 0" tone="error" size="xs" dot>
            {{ removedCols.size }} removida{{ removedCols.size !== 1 ? "s" : "" }}
          </AppPill>
          <AppPill v-if="renamedMap.size > 0" tone="info" size="xs" dot>
            {{ renamedMap.size }} renomeada{{ renamedMap.size !== 1 ? "s" : "" }}
          </AppPill>
          <AppPill v-if="derivedCols.size > 0" tone="success" size="xs" dot>
            {{ derivedCols.size }} derivada{{ derivedCols.size !== 1 ? "s" : "" }}
          </AppPill>
          <AppPill tone="neutral" size="xs">
            {{ changedCount }} / {{ aligned.length }} linhas alteradas
          </AppPill>
        </div>

        <!-- Toolbar -->
        <div
          class="flex items-center gap-[10px] border-b border-[var(--border)] px-[18px] py-[8px]"
        >
          <EditorTabs
            v-model="view"
            :tabs="[
              { id: 'side', label: 'Lado a lado', icon: 'squares-2x2' },
              { id: 'unified', label: 'Unificado', icon: 'bars-3' },
            ]"
            size="sm"
          />
          <div class="flex-1" />
          <!-- Checkbox apenas linhas com mudanças -->
          <label class="flex cursor-pointer items-center gap-[6px]">
            <input
              v-model="onlyChanges"
              type="checkbox"
              class="h-[14px] w-[14px] cursor-pointer accent-[var(--brand-500)]"
            >
            <span class="text-[12px]" :style="{ color: 'var(--fg-secondary)' }">
              Apenas linhas com mudanças
            </span>
          </label>
          <!-- Exportar -->
          <AppButton
            v-if="onExport"
            variant="ghost"
            color="neutral"
            size="sm"
            icon="arrow-down-tray"
            @click="onExport()"
          >
            Exportar
          </AppButton>
        </div>

        <!-- Corpo -->
        <div class="comp-body">
          <!-- Vista lado a lado -->
          <template v-if="view === 'side'">
            <div class="comp-side-grid">
              <!-- Tabela ANTES -->
              <div class="flex flex-col gap-[8px]">
                <AppPill tone="neutral" size="xs" dot>Antes</AppPill>
                <div
                  ref="beforeRef"
                  class="comp-table-wrap"
                  @scroll="syncScroll('before')"
                >
                  <table class="comp-table">
                    <thead>
                      <tr>
                        <th
                          v-for="col in beforeCols"
                          :key="col"
                          class="comp-th"
                          :style="beforeHeaderStyle(col)"
                        >
                          {{ col }}
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr
                        v-for="(pair, ri) in displayedRows"
                        :key="ri"
                        class="comp-row"
                      >
                        <td
                          v-for="col in beforeCols"
                          :key="col"
                          class="comp-td"
                          :style="beforeCellStyle(col)"
                        >
                          <span v-if="pair.before[col] === null || pair.before[col] === undefined" :style="{ color: 'var(--fg-tertiary)' }">—</span>
                          <span v-else>{{ pair.before[col] }}</span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              <!-- Tabela DEPOIS -->
              <div class="flex flex-col gap-[8px]">
                <AppPill tone="success" size="xs" dot>Depois</AppPill>
                <div
                  ref="afterRef"
                  class="comp-table-wrap"
                  @scroll="syncScroll('after')"
                >
                  <table class="comp-table">
                    <thead>
                      <tr>
                        <th
                          v-for="col in afterCols"
                          :key="col"
                          class="comp-th"
                          :style="afterHeaderStyle(col)"
                        >
                          {{ col }}
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr
                        v-for="(pair, ri) in displayedRows"
                        :key="ri"
                        class="comp-row"
                      >
                        <td
                          v-for="col in afterCols"
                          :key="col"
                          class="comp-td"
                          :style="afterCellStyle(col)"
                        >
                          <span v-if="pair.after[col] === null || pair.after[col] === undefined" :style="{ color: 'var(--fg-tertiary)' }">—</span>
                          <span v-else>{{ pair.after[col] }}</span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </template>

          <!-- Vista unificada -->
          <template v-else>
            <div class="flex flex-col gap-[12px]">
              <div
                v-for="(pair, ri) in displayedRows"
                :key="ri"
                class="rounded-[var(--radius-md)] border border-[var(--border)] overflow-hidden"
              >
                <!-- Cabeçalho da linha -->
                <div
                  class="flex items-center gap-[8px] px-[10px] py-[6px]"
                  :style="{ background: 'var(--surface-elevated)', borderBottom: '1px solid var(--border)' }"
                >
                  <span class="font-mono text-[10px]" :style="{ color: 'var(--fg-tertiary)' }">
                    Linha {{ ri + 1 }}
                  </span>
                  <AppPill v-if="rowHasChange(pair)" tone="warning" size="xs">alterada</AppPill>
                </div>
                <!-- Conteúdo por coluna -->
                <div
                  v-for="col in allUnifiedCols"
                  :key="col"
                  class="grid items-start border-b border-[var(--border)] last:border-b-0"
                  style="grid-template-columns: auto 1fr 1fr"
                >
                  <span
                    class="px-[10px] py-[5px] font-mono text-[10px] font-semibold"
                    :style="{ color: 'var(--fg-tertiary)', minWidth: '140px', borderRight: '1px solid var(--border)' }"
                  >
                    {{ col }}
                  </span>
                  <!-- Valor antes -->
                  <span
                    class="px-[10px] py-[5px] font-mono text-[11px]"
                    :style="{ color: removedCols.has(col) ? 'var(--status-error)' : 'var(--fg-secondary)', borderRight: '1px solid var(--border)', textDecoration: removedCols.has(col) ? 'line-through' : 'none' }"
                  >
                    {{ pair.before[col] ?? "—" }}
                  </span>
                  <!-- Valor depois -->
                  <span
                    class="px-[10px] py-[5px] font-mono text-[11px]"
                    :style="{ color: derivedCols.has(col) ? 'var(--status-success)' : renamedMap.has(col) ? 'var(--status-info)' : 'var(--fg-secondary)' }"
                  >
                    {{ pair.after[col] ?? "—" }}
                  </span>
                </div>
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { useEventListener } from "@vueuse/core"
import type { PreviewResultV2 } from "~/types/pipeline-editor-v2"

const props = withDefaults(
  defineProps<{
    open: boolean
    preview?: PreviewResultV2 | null
    onExport?: ((...args: unknown[]) => unknown) | null
  }>(),
  {
    preview: null,
    onExport: null,
  },
)

const emit = defineEmits<{
  close: []
}>()

// Estado do modal
const view = ref<"side" | "unified">("side")
const onlyChanges = ref(false)
const beforeRef = ref<HTMLElement | null>(null)
const afterRef = ref<HTMLElement | null>(null)
let syncing = false

// Computed: conjuntos derivados do schemaDelta
const removedCols = computed(() => new Set(props.preview?.schemaDelta?.removed ?? []))

const renamedMap = computed(() => {
  const map = new Map<string, string>()
  for (const r of (props.preview?.schemaDelta?.renamed ?? [])) {
    map.set(r.from, r.to)
  }
  return map
})

const derivedCols = computed(() => {
  const items = props.preview?.schemaDelta?.derived ?? []
  return new Set(items.map((d) => (typeof d === "string" ? d : d.name)))
})

// Alinhamento de linhas antes/depois
const aligned = computed(() => {
  const before = props.preview?.rowsBefore ?? []
  const after = props.preview?.rowsAfter ?? []
  return before.map((b, i) => ({ before: b, after: after[i] ?? {} }))
})

function rowHasChange(pair: { before: Record<string, unknown>; after: Record<string, unknown> }) {
  const allCols = new Set([...Object.keys(pair.before), ...Object.keys(pair.after)])
  for (const col of allCols) {
    if (String(pair.before[col] ?? "") !== String(pair.after[col] ?? "")) return true
  }
  return false
}

const changedCount = computed(() => aligned.value.filter(rowHasChange).length)

// Linhas a exibir (filtradas ou não)
const displayedRows = computed(() =>
  onlyChanges.value ? aligned.value.filter(rowHasChange) : aligned.value,
)

// Colunas de cada tabela
const beforeCols = computed(() =>
  props.preview?.rowsBefore?.[0] ? Object.keys(props.preview.rowsBefore[0]) : [],
)

const afterCols = computed(() =>
  props.preview?.rowsAfter?.[0] ? Object.keys(props.preview.rowsAfter[0]) : [],
)

// Colunas unificadas (união de antes + depois)
const allUnifiedCols = computed(() => {
  const s = new Set([...beforeCols.value, ...afterCols.value])
  return Array.from(s)
})

// Estilos de cabeçalho para tabela ANTES
function beforeHeaderStyle(col: string): Record<string, string> {
  if (removedCols.value.has(col)) {
    return { color: "var(--status-error)", background: "rgba(239,68,68,0.08)" }
  }
  if (renamedMap.value.has(col)) {
    return { color: "var(--status-info)", background: "rgba(59,130,246,0.08)" }
  }
  return { color: "var(--fg-secondary)", background: "var(--surface-elevated)" }
}

// Estilos de cabeçalho para tabela DEPOIS
function afterHeaderStyle(col: string): Record<string, string> {
  if (derivedCols.value.has(col)) {
    return { color: "var(--status-success)", background: "rgba(34,197,94,0.08)" }
  }
  if (Array.from(renamedMap.value.values()).includes(col)) {
    return { color: "var(--status-info)", background: "rgba(59,130,246,0.08)" }
  }
  return { color: "var(--fg-secondary)", background: "var(--surface-elevated)" }
}

// Estilos de célula ANTES
function beforeCellStyle(col: string): Record<string, string> {
  if (removedCols.value.has(col)) {
    return { color: "var(--status-error)", textDecoration: "line-through", opacity: "0.7" }
  }
  return { color: "var(--fg-secondary)" }
}

// Estilos de célula DEPOIS
function afterCellStyle(col: string): Record<string, string> {
  if (derivedCols.value.has(col)) return { color: "var(--status-success)" }
  if (Array.from(renamedMap.value.values()).includes(col)) return { color: "var(--status-info)" }
  return { color: "var(--fg-secondary)" }
}

// Scroll sincronizado entre as duas tabelas
function syncScroll(source: "before" | "after") {
  if (syncing) return
  syncing = true
  const fromEl = source === "before" ? beforeRef.value : afterRef.value
  const toEl = source === "before" ? afterRef.value : beforeRef.value
  if (fromEl && toEl) {
    toEl.scrollTop = fromEl.scrollTop
    toEl.scrollLeft = fromEl.scrollLeft
  }
  requestAnimationFrame(() => { syncing = false })
}

// Fecha com Escape
useEventListener("keydown", (e: KeyboardEvent) => {
  if (e.key === "Escape" && props.open) emit("close")
})
</script>

<style scoped>
.comp-backdrop {
  position: fixed;
  inset: 0;
  z-index: 300;
  background: rgba(9, 10, 11, 0.82);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  animation: fade-in 180ms ease-out;
}

.comp-modal {
  width: 100%;
  max-width: 1400px;
  max-height: calc(100vh - 48px);
  display: flex;
  flex-direction: column;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-medium);
  overflow: hidden;
  animation: modal-pop 200ms ease-out;
}

.comp-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  gap: 12px;
}

.comp-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--fg-primary);
  margin: 0;
}

.comp-body {
  flex: 1;
  overflow: auto;
  padding: 16px 18px;
}

.comp-side-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.comp-table-wrap {
  overflow: auto;
  max-height: calc(100vh - 260px);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}

.comp-table {
  width: 100%;
  border-collapse: collapse;
  font-family: var(--font-mono);
  font-size: 11px;
}

.comp-th {
  position: sticky;
  top: 0;
  padding: 6px 10px;
  font-size: 10px;
  font-weight: 600;
  white-space: nowrap;
  border-bottom: 1px solid var(--border);
  text-align: left;
}

.comp-row {
  border-bottom: 1px solid var(--border);
}

.comp-row:last-child {
  border-bottom: none;
}

.comp-td {
  padding: 5px 10px;
  white-space: nowrap;
}

@keyframes fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes modal-pop {
  from { opacity: 0; transform: scale(0.97) translateY(6px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}
</style>
