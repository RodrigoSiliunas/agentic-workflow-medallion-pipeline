<script setup lang="ts">
import { useEventListener } from "@vueuse/core"
import type { FileDiff } from "~/types/pipeline-editor-v2"

// ---------------------------------------------------------------------------
// Props & emits
// ---------------------------------------------------------------------------
const props = withDefaults(defineProps<{
  open: boolean
  files?: FileDiff[]
  initialPath?: string | null
  sessionId: string
}>(), {
  files: () => [],
  initialPath: null,
})

const emit = defineEmits<{
  close: []
}>()

// ---------------------------------------------------------------------------
// Estado local
// ---------------------------------------------------------------------------
const activePath = ref(props.initialPath || props.files[0]?.path || "")
const view = ref<"unified" | "split">("unified")

// Sincroniza path quando initialPath ou open mudam
watch(
  () => props.initialPath,
  (v) => {
    if (props.open && v) activePath.value = v
  }
)

watch(
  () => props.open,
  (v) => {
    if (v && !activePath.value && props.files[0]) {
      activePath.value = props.files[0].path
    }
  }
)

// ---------------------------------------------------------------------------
// Arquivo ativo + totais
// ---------------------------------------------------------------------------
const file = computed(
  () => props.files.find((f) => f.path === activePath.value) || props.files[0] || null
)

const totalAdditions = computed(() =>
  props.files.reduce((acc, f) => acc + f.additions, 0)
)

const totalDeletions = computed(() =>
  props.files.reduce((acc, f) => acc + f.deletions, 0)
)

// ---------------------------------------------------------------------------
// Navegação por teclado
// ---------------------------------------------------------------------------
function nextFile() {
  const idx = props.files.findIndex((f) => f.path === activePath.value)
  if (idx < props.files.length - 1) {
    activePath.value = props.files[idx + 1].path
  }
}

function prevFile() {
  const idx = props.files.findIndex((f) => f.path === activePath.value)
  if (idx > 0) {
    activePath.value = props.files[idx - 1].path
  }
}

useEventListener("keydown", (e: KeyboardEvent) => {
  if (!props.open) return
  if (e.key === "Escape") emit("close")
  if (e.key === "ArrowDown" || e.key === "j") nextFile()
  if (e.key === "ArrowUp" || e.key === "k") prevFile()
})

// ---------------------------------------------------------------------------
// Kebab menu
// ---------------------------------------------------------------------------
function copyPath() {
  if (file.value) navigator.clipboard.writeText(file.value.path)
}

const kebabItems = computed(() => [
  { icon: "clipboard-document", label: "Copiar caminho", onClick: copyPath },
  { icon: "arrow-down-tray", label: "Download patch", onClick: () => {} },
  { icon: "arrow-top-right-on-square", label: "Abrir no GitHub", onClick: () => {} },
  { icon: "chat-bubble-left-ellipsis", label: "Comentar diff", onClick: () => {} },
])

// ---------------------------------------------------------------------------
// Helpers de exibição
// ---------------------------------------------------------------------------
function fileBasename(path: string) {
  return path.split("/").pop() ?? path
}

function fileDir(path: string) {
  const parts = path.split("/")
  return parts.length > 1 ? parts.slice(0, -1).join("/") : ""
}

// Tabs para EditorTabs (unified/split)
const viewTabs = [
  { id: "unified", label: "Unificado" },
  { id: "split", label: "Lado a lado" },
]
</script>

<template>
  <!-- Backdrop -->
  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="open"
        class="backdrop"
        @click.self="emit('close')"
      >
        <!-- Modal inner -->
        <div class="modal" role="dialog" aria-modal="true" aria-label="Diff dos arquivos">
          <!-- Cabeçalho -->
          <div class="modal-header">
            <div class="header-left">
              <div class="header-icon-box">
                <AppIcon name="code-bracket" size="sm" />
              </div>
              <span class="header-title">Diff dos arquivos</span>
              <AppCode>pipeline-editor/{{ sessionId }}</AppCode>
            </div>

            <div class="header-right">
              <!-- Total de adições/remoções -->
              <div class="total-pill">
                <span class="added">+{{ totalAdditions }}</span>
                <span class="sep">/</span>
                <span class="removed">-{{ totalDeletions }}</span>
              </div>

              <!-- Seletor de visualização -->
              <EditorTabs
                :tabs="viewTabs"
                :model-value="view"
                size="sm"
                @update:model-value="view = $event as 'unified' | 'split'"
              />

              <!-- Fechar -->
              <AppIconBtn
                icon="x-mark"
                label="Fechar modal"
                :size="28"
                @click="emit('close')"
              />
            </div>
          </div>

          <!-- Corpo: rail + conteúdo principal -->
          <div class="modal-body">
            <!-- Rail esquerda: lista de arquivos -->
            <aside class="file-rail">
              <div class="rail-header">Arquivos ({{ files.length }})</div>

              <div class="rail-list">
                <button
                  v-for="f in files"
                  :key="f.path"
                  class="rail-btn"
                  :class="{ active: f.path === activePath }"
                  @click="activePath = f.path"
                >
                  <AppIcon name="document-text" size="xs" />
                  <div class="rail-file-info">
                    <span class="rail-file-name">{{ fileBasename(f.path) }}</span>
                    <span v-if="fileDir(f.path)" class="rail-file-dir">{{ fileDir(f.path) }}</span>
                  </div>
                  <div class="rail-file-stats">
                    <span class="added">+{{ f.additions }}</span>
                    <span class="removed">-{{ f.deletions }}</span>
                  </div>
                </button>
              </div>

              <!-- Dica de teclado -->
              <div class="rail-footer">
                <AppKbd>↑</AppKbd>
                <AppKbd>↓</AppKbd>
                <span class="kbd-hint">navegar</span>
              </div>
            </aside>

            <!-- Área principal: conteúdo do diff -->
            <div class="diff-area">
              <!-- Sub-cabeçalho do arquivo ativo -->
              <div v-if="file" class="diff-subheader">
                <AppIcon name="document-text" size="xs" />
                <AppCode>{{ file.path }}</AppCode>
                <span class="diff-stats">
                  <span class="added">+{{ file.additions }}</span>
                  <span class="removed"> -{{ file.deletions }}</span>
                </span>
                <div class="diff-subheader-spacer" />
                <KebabMenu :items="kebabItems" />
              </div>

              <!-- Visualização do diff -->
              <div class="diff-scroll">
                <!-- Sem arquivo selecionado -->
                <div v-if="!file" class="diff-empty">
                  <AppIcon name="document-magnifying-glass" size="lg" />
                  <span>Selecione um arquivo</span>
                </div>

                <!-- Sem linhas no arquivo -->
                <div v-else-if="!file.lines || file.lines.length === 0" class="diff-empty">
                  <AppIcon name="document-check" size="lg" />
                  <span>Sem linhas de diff disponíveis</span>
                </div>

                <!-- Visualização unificada -->
                <template v-else-if="view === 'unified'">
                  <div class="hunk-header">@@ diff unificado</div>
                  <div class="unified-grid">
                    <template v-for="(line, idx) in file.lines" :key="idx">
                      <div
                        class="line-row"
                        :class="line.type"
                      >
                        <!-- Número de linha antigo (removido) -->
                        <div class="line-num">
                          <span v-if="line.type === 'removed' || line.type === 'context'">
                            {{ line.lineNumber ?? idx + 1 }}
                          </span>
                        </div>
                        <!-- Número de linha novo (adicionado) -->
                        <div class="line-num">
                          <span v-if="line.type === 'added' || line.type === 'context'">
                            {{ line.lineNumber ?? idx + 1 }}
                          </span>
                        </div>
                        <!-- Símbolo -->
                        <div class="line-symbol">
                          <span v-if="line.type === 'added'">+</span>
                          <span v-else-if="line.type === 'removed'">-</span>
                          <span v-else />
                        </div>
                        <!-- Conteúdo da linha -->
                        <div class="line-content">
                          <code>{{ line.content }}</code>
                        </div>
                      </div>
                    </template>
                  </div>
                </template>

                <!-- Visualização lado a lado (split) -->
                <template v-else>
                  <div class="split-grid">
                    <!-- Coluna esquerda: linhas removidas + contexto -->
                    <div class="split-col">
                      <div class="split-col-header removed">Anterior</div>
                      <div
                        v-for="(line, idx) in file.lines.filter(
                          (l) => l.type === 'removed' || l.type === 'context'
                        )"
                        :key="'l-' + idx"
                        class="line-row"
                        :class="line.type"
                      >
                        <div class="line-num">{{ line.lineNumber ?? idx + 1 }}</div>
                        <div class="line-content"><code>{{ line.content }}</code></div>
                      </div>
                    </div>

                    <!-- Coluna direita: linhas adicionadas + contexto -->
                    <div class="split-col">
                      <div class="split-col-header added">Novo</div>
                      <div
                        v-for="(line, idx) in file.lines.filter(
                          (l) => l.type === 'added' || l.type === 'context'
                        )"
                        :key="'r-' + idx"
                        class="line-row"
                        :class="line.type"
                      >
                        <div class="line-num">{{ line.lineNumber ?? idx + 1 }}</div>
                        <div class="line-content"><code>{{ line.content }}</code></div>
                      </div>
                    </div>
                  </div>
                </template>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* Backdrop escuro com blur */
.backdrop {
  position: fixed;
  inset: 0;
  z-index: 300;
  background: rgba(0, 0, 0, 0.55);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

/* Transição de entrada */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.18s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Modal */
.modal {
  max-width: 1400px;
  max-height: 900px;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  overflow: hidden;
  animation: modal-pop 0.18s ease;
}

@keyframes modal-pop {
  from {
    opacity: 0;
    transform: scale(0.97) translateY(6px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

/* Cabeçalho do modal */
.modal-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.header-icon-box {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  background: var(--surface-elevated);
  border: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.header-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--fg-primary);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

/* Pill de totais */
.total-pill {
  display: flex;
  align-items: center;
  gap: 3px;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--surface-elevated);
  border: 1px solid var(--border);
  font-family: var(--font-mono);
  font-size: 11px;
}

.sep {
  color: var(--fg-tertiary);
}

/* Corpo do modal */
.modal-body {
  display: flex;
  flex-direction: row;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

/* Rail de arquivos */
.file-rail {
  width: 280px;
  flex-shrink: 0;
  border-right: 1px solid var(--border);
  background: color-mix(in srgb, var(--bg) 60%, var(--surface));
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.rail-header {
  padding: 10px 12px 8px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--fg-tertiary);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.rail-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px;
}

.rail-btn {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  border-radius: var(--radius-sm);
  border: none;
  background: transparent;
  cursor: pointer;
  color: var(--fg-primary);
  text-align: left;
  transition: background 0.12s;
  border-left: 2px solid transparent;
}

.rail-btn:hover {
  background: var(--surface-elevated);
}

.rail-btn.active {
  background: color-mix(in srgb, var(--brand-500) 10%, transparent);
  border-left-color: var(--brand-500);
}

.rail-file-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.rail-file-name {
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rail-file-dir {
  font-size: 10px;
  color: var(--fg-tertiary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rail-file-stats {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  font-family: var(--font-mono);
  font-size: 10px;
  gap: 1px;
}

.rail-footer {
  padding: 8px 12px;
  border-top: 1px solid var(--border);
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.kbd-hint {
  font-size: 11px;
  color: var(--fg-tertiary);
  margin-left: 2px;
}

/* Área de diff */
.diff-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}

.diff-subheader {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.diff-subheader-spacer {
  flex: 1;
}

.diff-stats {
  font-family: var(--font-mono);
  font-size: 12px;
}

.diff-scroll {
  flex: 1;
  overflow: auto;
  background: var(--bg);
}

/* Estado vazio */
.diff-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 100%;
  color: var(--fg-tertiary);
  font-size: 13px;
}

/* Cabeçalho de hunk */
.hunk-header {
  padding: 4px 14px;
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--fg-tertiary);
  background: color-mix(in srgb, var(--surface-elevated) 50%, transparent);
  border-bottom: 1px solid var(--border);
}

/* Grade unificada: 56px 56px 24px 1fr */
.unified-grid {
  display: flex;
  flex-direction: column;
}

.line-row {
  display: grid;
  grid-template-columns: 56px 56px 24px 1fr;
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.5;
  min-height: 22px;
}

.line-row.added {
  background: color-mix(in srgb, var(--status-success) 10%, transparent);
}

.line-row.removed {
  background: color-mix(in srgb, var(--status-error) 10%, transparent);
}

.line-row.context {
  background: transparent;
}

.line-num {
  padding: 0 8px;
  text-align: right;
  color: var(--fg-tertiary);
  user-select: none;
  border-right: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: flex-end;
}

.line-symbol {
  padding: 0 4px;
  text-align: center;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--fg-secondary);
}

.line-row.added .line-symbol {
  color: var(--status-success);
}

.line-row.removed .line-symbol {
  color: var(--status-error);
}

.line-content {
  padding: 0 12px;
  white-space: pre;
  overflow: hidden;
  display: flex;
  align-items: center;
}

.line-content code {
  font-family: inherit;
  font-size: inherit;
}

/* Visualização split */
.split-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  height: 100%;
}

.split-col {
  display: flex;
  flex-direction: column;
  overflow: auto;
  border-right: 1px solid var(--border);
}

.split-col:last-child {
  border-right: none;
}

.split-col-header {
  padding: 4px 12px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  z-index: 1;
  background: var(--surface-elevated);
}

.split-col-header.added {
  color: var(--status-success);
}

.split-col-header.removed {
  color: var(--status-error);
}

/* Cores globais dos stats */
.added {
  color: var(--status-success);
}

.removed {
  color: var(--status-error);
}
</style>
