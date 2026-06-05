<script setup lang="ts">
import type { PipelineEditSession, SessionStatusV2 } from "~/types/pipeline-editor-v2"

// Visão de histórico de sessões do pipeline editor
const props = defineProps<{
  sessions: PipelineEditSession[]
}>()

const emit = defineEmits<{
  select: [id: string]
  close: []
}>()

// Filtros locais da tabela
const search = ref("")
const statusFilter = ref("all")

// Opções de filtro por status
const statusOptions = [
  { value: "all", label: "Todos os status" },
  { value: "draft", label: "Rascunho" },
  { value: "preview_ok", label: "Preview OK" },
  { value: "pr_created", label: "PR criado" },
  { value: "validated", label: "Validado" },
  { value: "validation_failed", label: "Falhou" }
]

// Sessões filtradas por busca e status
const filteredSessions = computed(() => {
  return props.sessions.filter((s) => {
    const matchesSearch =
      !search.value ||
      s.title.toLowerCase().includes(search.value.toLowerCase()) ||
      s.id.toLowerCase().includes(search.value.toLowerCase())
    const matchesStatus =
      statusFilter.value === "all" || s.status === statusFilter.value
    return matchesSearch && matchesStatus
  })
})

// Tone do AppPill baseado no status da sessão
function statusTone(
  status: SessionStatusV2
): "success" | "error" | "info" | "warning" | "neutral" {
  const map: Record<SessionStatusV2, "success" | "error" | "info" | "warning" | "neutral"> = {
    pr_created: "success",
    validation_failed: "error",
    validated: "success",
    preview_ok: "info",
    draft: "warning"
  }
  return map[status] ?? "neutral"
}

// Label legível do status
function statusLabel(status: SessionStatusV2): string {
  const map: Record<SessionStatusV2, string> = {
    draft: "Rascunho",
    preview_ok: "Preview OK",
    pr_created: "PR criado",
    validated: "Validado",
    validation_failed: "Falhou"
  }
  return map[status] ?? status
}

// Tone do risco baseado no score
function riskTone(score?: number): "success" | "warning" | "error" | "neutral" {
  if (score === undefined) return "neutral"
  if (score <= 3) return "success"
  if (score <= 6) return "warning"
  return "error"
}
</script>

<template>
  <!-- Layout de tela cheia para histórico de sessões -->
  <div class="history-view">
    <!-- Cabeçalho com navegação e filtros -->
    <header class="history-header">
      <div class="header-left">
        <AppIconBtn
          icon="arrow-left"
          label="Voltar"
          :size="28"
          @click="emit('close')"
        />
        <SectionHeader overline="Histórico" title="Sessões anteriores" />
      </div>
      <div class="header-filters">
        <AppInput
          v-model="search"
          icon="magnifying-glass"
          placeholder="Buscar sessões..."
          size="sm"
          class="history-search"
        />
        <AppSelect
          v-model="statusFilter"
          :options="statusOptions"
          size="sm"
          class="history-status-filter"
        />
      </div>
    </header>

    <!-- Tabela de sessões -->
    <div class="history-table-wrapper">
      <table class="history-table">
        <thead>
          <tr>
            <th class="col-title">Título</th>
            <th class="col-status">Status</th>
            <th class="col-author">Autor</th>
            <th class="col-date">Atualizada</th>
            <th class="col-risk">Risco</th>
            <th class="col-pr">PR</th>
            <th class="col-actions" />
          </tr>
        </thead>
        <tbody>
          <!-- Linha de sessão -->
          <tr
            v-for="session in filteredSessions"
            :key="session.id"
            class="history-row"
          >
            <!-- Título + código do id -->
            <td class="col-title">
              <div class="title-cell">
                <span class="session-title">{{ session.title }}</span>
                <AppCode class="session-id">#{{ session.id }}</AppCode>
              </div>
            </td>

            <!-- Status como pill -->
            <td class="col-status">
              <AppPill
                :tone="statusTone(session.status)"
                size="xs"
              >
                {{ statusLabel(session.status) }}
              </AppPill>
            </td>

            <!-- Autor com avatar -->
            <td class="col-author">
              <div class="author-cell">
                <AppAvatar
                  :name="session.author ?? 'Anônimo'"
                  :size="22"
                />
                <span class="author-name">{{ session.author ?? "—" }}</span>
              </div>
            </td>

            <!-- Data de atualização em mono -->
            <td class="col-date">
              <span class="date-mono">{{ session.updatedAt ?? "—" }}</span>
            </td>

            <!-- Risco como pill com score -->
            <td class="col-risk">
              <AppPill
                v-if="session.riskScore !== undefined"
                :tone="riskTone(session.riskScore)"
                size="xs"
              >
                {{ session.riskScore }}/10
              </AppPill>
              <span v-else class="empty-cell">—</span>
            </td>

            <!-- Link para o PR no GitHub -->
            <td class="col-pr">
              <a
                v-if="session.prNumber"
                :href="`https://github.com/RodrigoSiliunas/agentic-workflow-medallion-pipeline/pull/${session.prNumber}`"
                target="_blank"
                rel="noopener noreferrer"
                class="pr-link"
              >
                <AppIcon name="arrow-top-right-on-square" size="xs" />
                #{{ session.prNumber }}
              </a>
              <span v-else class="empty-cell">—</span>
            </td>

            <!-- Ação de continuar sessão -->
            <td class="col-actions">
              <AppButton
                variant="ghost"
                color="neutral"
                size="xs"
                @click="emit('select', session.id)"
              >
                Continuar
              </AppButton>
            </td>
          </tr>

          <!-- Estado vazio quando não há resultados -->
          <tr v-if="filteredSessions.length === 0">
            <td colspan="7" class="empty-state">
              <AppIcon name="inbox" size="lg" class="empty-icon" />
              <span class="empty-text">Nenhuma sessão encontrada</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
/* Layout raiz */
.history-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--surface);
}

/* Cabeçalho fixo */
.history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
  gap: 16px;
  flex-shrink: 0;
  flex-wrap: wrap;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-filters {
  display: flex;
  gap: 8px;
  align-items: center;
}

.history-search {
  width: 220px;
}

.history-status-filter {
  width: 160px;
}

/* Wrapper com scroll da tabela */
.history-table-wrapper {
  flex: 1;
  overflow: auto;
}

/* Tabela principal */
.history-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

/* Cabeçalho sticky */
.history-table thead th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: var(--surface-elevated);
  border-bottom: 1px solid var(--border);
  padding: 8px 12px;
  font-size: 11px;
  font-weight: 600;
  color: var(--fg-tertiary);
  text-align: left;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  white-space: nowrap;
}

/* Linhas da tabela */
.history-row {
  border-bottom: 1px solid var(--border);
  transition: background 100ms ease;
}

.history-row:hover {
  background: var(--surface-elevated);
}

.history-table td {
  padding: 10px 12px;
  vertical-align: middle;
}

/* Célula de título */
.title-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.session-title {
  font-weight: 500;
  color: var(--fg-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 200px;
}

.session-id {
  align-self: flex-start;
}

/* Célula de autor */
.author-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.author-name {
  color: var(--fg-secondary);
  white-space: nowrap;
}

/* Data em fonte mono */
.date-mono {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--fg-secondary);
  white-space: nowrap;
}

/* Link para PR */
.pr-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--brand-500);
  text-decoration: none;
  white-space: nowrap;
}

.pr-link:hover {
  text-decoration: underline;
  color: var(--brand-600);
}

/* Placeholder de célula vazia */
.empty-cell {
  color: var(--fg-tertiary);
}

/* Estado vazio */
.empty-state {
  text-align: center;
  padding: 48px 16px !important;
}

.empty-icon {
  color: var(--fg-tertiary);
  display: block;
  margin: 0 auto 12px;
}

.empty-text {
  font-size: 14px;
  color: var(--fg-tertiary);
}

/* Larguras fixas das colunas */
.col-title {
  min-width: 200px;
}

.col-status {
  width: 110px;
  white-space: nowrap;
}

.col-author {
  width: 140px;
  white-space: nowrap;
}

.col-date {
  width: 130px;
  white-space: nowrap;
}

.col-risk {
  width: 80px;
  white-space: nowrap;
}

.col-pr {
  width: 72px;
  white-space: nowrap;
}

.col-actions {
  width: 88px;
  text-align: right;
}
</style>
