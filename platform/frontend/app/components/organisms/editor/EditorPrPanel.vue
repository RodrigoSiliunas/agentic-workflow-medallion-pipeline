<script setup lang="ts">
import type {
  EditProposal,
  PreviewResultV2,
  ValidationResult,
  PipelineEditSession,
  FileDiff
} from "~/types/pipeline-editor-v2"
// ---------------------------------------------------------------------------
// Props & emits
// ---------------------------------------------------------------------------
const props = withDefaults(defineProps<{
  proposal: EditProposal | null
  preview: PreviewResultV2 | null
  validation: ValidationResult | null
  session: PipelineEditSession
  fileDiffs?: FileDiff[]
}>(), {
  fileDiffs: () => [],
})

const emit = defineEmits<{
  approve: []
  share: []
  revert: []
}>()

// ---------------------------------------------------------------------------
// Computed — lógica de aprovação
// ---------------------------------------------------------------------------
const canApprove = computed(
  () =>
    props.preview?.status === "ready" &&
    props.validation?.valid &&
    props.session.status !== "pr_created"
)

const blockMsg = computed<string | null>(() => {
  if (props.session.status === "pr_created") {
    return "PR já aberto para esta sessão."
  }
  if (!props.preview) {
    return "Rode o preview antes de aprovar."
  }
  if (props.preview.status !== "ready") {
    return `Preview não está pronto (status atual: ${props.preview.status}).`
  }
  if (props.validation && !props.validation.valid) {
    return "Validação rejeitou — corrija antes de aprovar."
  }
  return null
})

// ---------------------------------------------------------------------------
// Estado local — diff modal
// ---------------------------------------------------------------------------
const diffOpen = ref(false)
const diffInitialPath = ref<string | null>(null)

function openDiff(path?: string) {
  diffInitialPath.value = path ?? null
  diffOpen.value = true
}

// ---------------------------------------------------------------------------
// Checks padrão quando validação ainda não rodou
// ---------------------------------------------------------------------------
const defaultChecks = [
  { label: "Codegen PySpark", state: "pending" as const },
  { label: "Ruff lint", state: "pending" as const },
  { label: "Schema compatível", state: "pending" as const },
  { label: "Marker injetado", state: "pending" as const },
]
</script>

<template>
  <!-- Painel de pull request — resumo de branch, arquivos, validação e ações -->
  <div class="pr-panel">
    <!-- Cabeçalho da seção -->
    <SectionHeader
      overline="Pull request"
      :title="session.status === 'pr_created' ? 'PR aberto' : 'Pronto para aprovar'"
    />

    <!-- Card: branch + arquivos + risk gauge -->
    <div class="info-card">
      <!-- Esquerda: branch e lista de arquivos -->
      <div class="info-left">
        <!-- Branch proposto -->
        <div class="meta-group">
          <span class="overline">Branch proposto</span>
          <AppCode>pipeline-editor/{{ session.id }}</AppCode>
          <span class="base-ref">base: dev</span>
        </div>

        <!-- Lista de arquivos afetados -->
        <div class="meta-group">
          <span class="overline">Arquivos ({{ fileDiffs.length }})</span>

          <AppButton
            v-if="fileDiffs.length > 0"
            variant="ghost"
            color="neutral"
            size="xs"
            icon="eye"
            @click="openDiff()"
          >
            Ver diff
          </AppButton>

          <button
            v-for="file in fileDiffs"
            :key="file.path"
            class="file-btn"
            @click="openDiff(file.path)"
          >
            <AppIcon name="document-text" size="xs" />
            <span class="file-path">{{ file.path }}</span>
            <span class="file-stats">
              <span class="added">+{{ file.additions }}</span>
              <span class="removed">-{{ file.deletions }}</span>
            </span>
            <AppIcon name="arrow-top-right-on-square" size="xs" class="file-ext" />
          </button>

          <p v-if="fileDiffs.length === 0" class="empty-files">
            Nenhum arquivo afetado ainda.
          </p>
        </div>
      </div>

      <!-- Direita: risk gauge -->
      <div class="info-right">
        <span class="overline">Risco</span>
        <AppRiskGauge :value="proposal?.riskScore ?? 0" :size="84" />
      </div>
    </div>

    <!-- Card: validação -->
    <div class="validation-card">
      <span class="card-title">Validação</span>
      <div class="check-list">
        <div
          v-for="(check, idx) in (validation?.checks || defaultChecks)"
          :key="idx"
          class="check-row"
        >
          <!-- Ícone de estado -->
          <template v-if="check.state === 'ok'">
            <AppIcon name="check-circle" size="sm" class="check-icon ok" />
          </template>
          <template v-else-if="check.state === 'fail'">
            <AppIcon name="x-circle" size="sm" class="check-icon fail" />
          </template>
          <template v-else-if="check.state === 'running'">
            <AppStatusDot tone="warning" :pulse="true" :size="6" />
          </template>
          <template v-else>
            <!-- pending -->
            <AppIcon name="clock" size="sm" class="check-icon pending" />
          </template>

          <span class="check-label">{{ check.label }}</span>
        </div>
      </div>
    </div>

    <!-- Ações -->
    <div class="actions">
      <!-- Aviso de bloqueio -->
      <div
        v-if="!canApprove && session.status !== 'pr_created' && blockMsg"
        class="block-msg"
      >
        <AppIcon name="lock-closed" size="xs" />
        <span>{{ blockMsg }}</span>
      </div>

      <!-- Estado: PR já criado -->
      <template v-if="session.status === 'pr_created'">
        <AppButton
          v-if="session.prUrl"
          :to="session.prUrl"
          target="_blank"
          rel="noopener noreferrer"
          variant="outline"
          color="neutral"
          icon="arrow-top-right-on-square"
          :block="true"
        >
          Ver PR #{{ session.prNumber }} no GitHub
        </AppButton>
        <AppButton
          v-else
          variant="outline"
          color="neutral"
          icon="arrow-top-right-on-square"
          :block="true"
          disabled
        >
          PR aberto (URL indisponível)
        </AppButton>

        <AppButton
          variant="outline"
          color="neutral"
          icon="code-bracket"
          :block="true"
          @click="openDiff()"
        >
          Ver diff completo
        </AppButton>

        <AppButton
          variant="outline"
          color="error"
          icon="arrow-uturn-left"
          :block="true"
          @click="emit('revert')"
        >
          Reverter PR
        </AppButton>
      </template>

      <!-- Estado: aguardando aprovação -->
      <template v-else>
        <AppButton
          color="primary"
          variant="solid"
          icon="check-circle"
          :disabled="!canApprove"
          :title="blockMsg ?? undefined"
          :block="true"
          @click="emit('approve')"
        >
          Aprovar e abrir PR
        </AppButton>

        <AppButton
          variant="ghost"
          color="neutral"
          icon="share"
          :block="true"
          @click="emit('share')"
        >
          Compartilhar sessão (read-only)
        </AppButton>
      </template>
    </div>

    <!-- Modal de diff de arquivos -->
    <EditorFileDiffModal
      :open="diffOpen"
      :files="fileDiffs"
      :initial-path="diffInitialPath"
      :session-id="session.id"
      @close="diffOpen = false"
    />
  </div>
</template>

<style scoped>
/* Layout raiz do painel */
.pr-panel {
  padding: 14px 14px 32px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  overflow-y: auto;
}

/* Card de informações: branch + risco */
.info-card {
  display: grid;
  grid-template-columns: 1fr 116px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
  overflow: hidden;
}

.info-left {
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.info-right {
  padding: 12px;
  border-left: 1px solid var(--border);
  background: color-mix(in srgb, var(--surface-elevated) 60%, transparent);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

/* Grupos de metadados */
.meta-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.overline {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--fg-tertiary);
}

.base-ref {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--fg-secondary);
}

/* Botões de arquivo */
.file-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 6px;
  border-radius: var(--radius-sm);
  background: transparent;
  border: none;
  cursor: pointer;
  width: 100%;
  text-align: left;
  color: var(--fg-primary);
  transition: background 0.15s;
}

.file-btn:hover {
  background: var(--surface-elevated);
}

.file-path {
  flex: 1;
  font-family: var(--font-mono);
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-stats {
  display: flex;
  gap: 4px;
  font-family: var(--font-mono);
  font-size: 11px;
}

.added {
  color: var(--status-success);
}

.removed {
  color: var(--status-error);
}

.file-ext {
  opacity: 0.4;
  flex-shrink: 0;
}

.empty-files {
  font-size: 12px;
  color: var(--fg-tertiary);
  margin: 0;
}

/* Card de validação */
.validation-card {
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
  background: var(--surface);
  overflow: hidden;
}

.card-title {
  display: block;
  padding: 10px 14px 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--fg-secondary);
  border-bottom: 1px solid var(--border);
}

.check-list {
  padding: 8px 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.check-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.check-icon {
  flex-shrink: 0;
}

.check-icon.ok {
  color: var(--status-success);
}

.check-icon.fail {
  color: var(--status-error);
}

.check-icon.pending {
  color: var(--fg-tertiary);
}

.check-label {
  font-size: 13px;
  color: var(--fg-primary);
}

/* Seção de ações */
.actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* Mensagem de bloqueio */
.block-msg {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 8px 10px;
  border-radius: var(--radius-md);
  background: color-mix(in srgb, var(--status-warning) 12%, transparent);
  border: 1px solid color-mix(in srgb, var(--status-warning) 30%, transparent);
  font-size: 12px;
  color: var(--fg-secondary);
  line-height: 1.4;
}
</style>
