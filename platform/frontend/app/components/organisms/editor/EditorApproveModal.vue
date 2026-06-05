<script setup lang="ts">
import type { EditProposal, PreviewResultV2, PipelineEditSession } from "~/types/pipeline-editor-v2"

// Modal de confirmação para abrir PR com alterações do pipeline editor
const props = defineProps<{
  open: boolean
  session: PipelineEditSession
  proposal: EditProposal | null
  preview: PreviewResultV2 | null
}>()

const emit = defineEmits<{
  close: []
  confirm: []
}>()

// Branch gerado a partir do id da sessão
const branch = computed(() => `pipeline-editor/${props.session.id}`)

// Tone do risco baseado no score
function riskTone(score?: number): "success" | "warning" | "error" | "neutral" {
  if (score === undefined) return "neutral"
  if (score <= 3) return "success"
  if (score <= 6) return "warning"
  return "error"
}

// Label do risco
function riskLabel(score?: number): string {
  if (score === undefined) return "N/A"
  if (score <= 3) return `Baixo (${score}/10)`
  if (score <= 6) return `Médio (${score}/10)`
  return `Alto (${score}/10)`
}

// Linhas simuladas por arquivo (mock estático para demo)
function mockLines(path: string): { add: number; del: number } {
  const hash = path.split("").reduce((acc, c) => acc + c.charCodeAt(0), 0)
  return { add: (hash % 40) + 5, del: (hash % 15) + 1 }
}
</script>

<template>
  <EditorModalShell
    :open="open"
    title="Aprovar e abrir PR"
    icon="code-bracket"
    icon-tone="brand"
    :width="560"
    @close="emit('close')"
  >
    <!-- Corpo do modal de aprovação -->
    <div class="approve-body">
      <!-- Descrição da ação -->
      <p class="approve-desc">
        Isso irá criar um pull request na branch
        <AppCode>{{ branch }}</AppCode>
        com base em
        <AppCode>dev</AppCode>.
        Revise as informações antes de confirmar.
      </p>

      <!-- Grid de metadados da sessão/proposta -->
      <div class="approve-meta-grid">
        <div class="meta-item">
          <span class="meta-label">Branch</span>
          <AppCode class="meta-value-code">{{ branch }}</AppCode>
        </div>
        <div class="meta-item">
          <span class="meta-label">Base</span>
          <AppCode class="meta-value-code">dev</AppCode>
        </div>
        <div class="meta-item">
          <span class="meta-label">Camada</span>
          <AppPill tone="info" size="xs" icon="circle-stack">Silver</AppPill>
        </div>
        <div class="meta-item">
          <span class="meta-label">Risco</span>
          <AppPill
            :tone="riskTone(proposal?.risk_score)"
            size="xs"
            icon="exclamation-triangle"
          >
            {{ riskLabel(proposal?.risk_score) }}
          </AppPill>
        </div>
      </div>

      <!-- Lista de arquivos afetados -->
      <div v-if="proposal?.files_affected?.length" class="approve-files">
        <p class="files-label">Arquivos alterados ({{ proposal.files_affected.length }})</p>
        <ul class="files-list">
          <li
            v-for="path in proposal.files_affected"
            :key="path"
            class="file-item"
          >
            <AppIcon name="document-text" size="xs" class="file-icon" />
            <span class="file-path">{{ path }}</span>
            <span class="file-diff">
              <span class="diff-add">+{{ mockLines(path).add }}</span>
              <span class="diff-del">-{{ mockLines(path).del }}</span>
            </span>
          </li>
        </ul>
      </div>

      <!-- Aviso sobre criação de PR real -->
      <div class="approve-warning">
        <AppIcon name="exclamation-triangle" size="sm" class="warning-icon" />
        <p class="warning-text">
          Esta ação cria um pull request real no repositório GitHub. Certifique-se de que
          o preview foi validado antes de prosseguir.
        </p>
      </div>
    </div>

    <!-- Rodapé com ações -->
    <template #footer>
      <div class="approve-footer">
        <div class="footer-hint">
          <AppKbd>Esc</AppKbd>
          <span class="hint-text">para cancelar</span>
        </div>
        <div class="footer-actions">
          <AppButton variant="ghost" color="neutral" size="sm" @click="emit('close')">
            Cancelar
          </AppButton>
          <AppButton
            variant="solid"
            color="primary"
            size="sm"
            icon="check-circle"
            @click="emit('confirm')"
          >
            Criar PR
          </AppButton>
        </div>
      </div>
    </template>
  </EditorModalShell>
</template>

<style scoped>
/* Corpo principal */
.approve-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Descrição inicial */
.approve-desc {
  font-size: 14px;
  color: var(--fg-secondary);
  line-height: 1.6;
  margin: 0;
}

/* Grid 2x2 de metadados */
.approve-meta-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1px;
  background: var(--border);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.meta-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px 14px;
  background: var(--surface-elevated);
}

.meta-label {
  font-size: 11px;
  font-weight: 500;
  color: var(--fg-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.meta-value-code {
  align-self: flex-start;
}

/* Lista de arquivos afetados */
.approve-files {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.files-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--fg-secondary);
  margin: 0;
}

.files-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  background: var(--surface-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.file-icon {
  color: var(--fg-tertiary);
  flex-shrink: 0;
}

.file-path {
  flex: 1;
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--fg-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-diff {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
  font-family: var(--font-mono);
  font-size: 12px;
}

.diff-add {
  color: var(--status-success);
}

.diff-del {
  color: var(--status-error);
}

/* Caixa de aviso */
.approve-warning {
  display: flex;
  gap: 10px;
  padding: 12px 14px;
  background: rgba(245, 158, 11, 0.08);
  border: 1px solid rgba(245, 158, 11, 0.25);
  border-radius: var(--radius-md);
}

.warning-icon {
  color: var(--status-warning);
  flex-shrink: 0;
  margin-top: 1px;
}

.warning-text {
  font-size: 13px;
  color: var(--fg-secondary);
  line-height: 1.5;
  margin: 0;
}

/* Rodapé */
.approve-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.footer-hint {
  display: flex;
  align-items: center;
  gap: 6px;
}

.hint-text {
  font-size: 12px;
  color: var(--fg-tertiary);
}

.footer-actions {
  display: flex;
  gap: 8px;
}
</style>
