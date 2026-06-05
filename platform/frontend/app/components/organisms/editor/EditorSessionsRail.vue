<script setup lang="ts">
import type { PipelineEditSession, SessionStatusV2 } from "~/types/pipeline-editor-v2"

// Rail lateral de navegação entre sessões de edição
const props = withDefaults(defineProps<{
  sessions?: PipelineEditSession[]
  activeId?: string
  collapsed?: boolean
}>(), {
  sessions: () => [],
  activeId: "",
  collapsed: false,
})

const emit = defineEmits<{
  select: [id: string]
  new: []
  toggle: []
}>()

// Mapeamento de status para tom visual
const STATUS_MAP: Record<SessionStatusV2, "warning" | "info" | "success" | "error"> = {
  draft:             "warning",
  preview_ok:        "info",
  pr_created:        "success",
  validated:         "success",
  validation_failed: "error",
}

// Rótulo legível do status
const STATUS_LABEL: Record<SessionStatusV2, string> = {
  draft:             "Rascunho",
  preview_ok:        "Preview ok",
  pr_created:        "PR criado",
  validated:         "Validado",
  validation_failed: "Falhou",
}

// Filtro de busca local
const searchQuery = ref("")

const filteredSessions = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return props.sessions
  return props.sessions.filter(
    (s) =>
      s.title.toLowerCase().includes(q) ||
      s.id.toLowerCase().includes(q) ||
      (s.author?.toLowerCase().includes(q) ?? false)
  )
})

// Formata a data de atualização de forma amigável
function formatDate(iso?: string): string {
  if (!iso) return "—"
  const d = new Date(iso)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffMin = Math.floor(diffMs / 60_000)
  if (diffMin < 1) return "agora"
  if (diffMin < 60) return `${diffMin}min atrás`
  const diffH = Math.floor(diffMin / 60)
  if (diffH < 24) return `${diffH}h atrás`
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" })
}
</script>

<template>
  <!-- Estado colapsado: rail estreita com ícones verticais -->
  <aside v-if="collapsed" class="rail rail--collapsed" aria-label="Sessões (colapsado)">
    <!-- Botão de toggle para expandir -->
    <button class="rail-toggle" type="button" :aria-label="'Expandir painel de sessões'" @click="emit('toggle')">
      <AppIcon name="chevron-double-right" size="sm" />
    </button>

    <!-- Atalho para nova sessão -->
    <AppIconBtn
      icon="plus"
      label="Nova sessão"
      :size="28"
      active
      @click="emit('new')"
    />

    <!-- Contagem de sessões em texto vertical -->
    <span class="rail-count-vertical" aria-hidden="true">
      {{ sessions.length }} sessões
    </span>
  </aside>

  <!-- Estado expandido: rail completa -->
  <aside v-else class="rail rail--expanded" aria-label="Sessões de edição">
    <!-- Cabeçalho do rail -->
    <div class="rail-header">
      <span class="rail-title">Sessões de edição</span>
      <button
        class="rail-toggle-btn"
        type="button"
        aria-label="Recolher painel de sessões"
        @click="emit('toggle')"
      >
        <AppIcon name="chevron-double-left" size="xs" />
      </button>
    </div>

    <!-- Botão nova sessão -->
    <div class="rail-new">
      <AppButton
        variant="solid"
        color="primary"
        icon="plus"
        block
        @click="emit('new')"
      >
        Nova sessão
      </AppButton>
    </div>

    <!-- Campo de busca -->
    <div class="rail-search">
      <AppInput
        v-model="searchQuery"
        placeholder="Filtrar..."
        size="sm"
        icon="magnifying-glass"
      />
    </div>

    <!-- Lista de sessões -->
    <ul class="sessions-list" role="listbox" aria-label="Lista de sessões">
      <li
        v-for="session in filteredSessions"
        :key="session.id"
        role="option"
        :aria-selected="session.id === activeId"
      >
        <button
          class="session-row"
          :class="{ 'session-row--active': session.id === activeId }"
          type="button"
          @click="emit('select', session.id)"
        >
          <!-- Ícone da sessão -->
          <div class="session-icon" aria-hidden="true">
            <AppIcon name="document-text" size="sm" />
          </div>

          <!-- Conteúdo da sessão -->
          <div class="session-body">
            <!-- Título + pill de status -->
            <div class="session-title-row">
              <span class="session-title">{{ session.title }}</span>
              <AppPill :tone="STATUS_MAP[session.status]" size="xs">
                {{ STATUS_LABEL[session.status] }}
              </AppPill>
            </div>

            <!-- Meta: ID + data + autor -->
            <div class="session-meta">
              <span class="session-id">#{{ session.id }}</span>
              <span class="session-sep" aria-hidden="true">·</span>
              <span class="session-date">{{ formatDate(session.updatedAt) }}</span>
              <template v-if="session.author">
                <span class="session-sep" aria-hidden="true">·</span>
                <span class="session-author">{{ session.author }}</span>
              </template>
            </div>
          </div>
        </button>
      </li>

      <!-- Estado vazio -->
      <li v-if="filteredSessions.length === 0" class="sessions-empty">
        <AppIcon name="magnifying-glass" size="sm" />
        <span>Nenhuma sessão encontrada</span>
      </li>
    </ul>

    <!-- Rodapé informativo -->
    <div class="rail-footer">
      <AppIcon name="information-circle" size="xs" />
      <span>Apenas camada Silver</span>
    </div>
  </aside>
</template>

<style scoped>
/* Base do rail */
.rail {
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border);
  background: var(--surface);
  height: 100%;
  flex-shrink: 0;
  overflow: hidden;
  transition: width 0.2s ease;
}

/* Rail colapsada */
.rail--collapsed {
  width: 44px;
  align-items: center;
  padding: 10px 0;
  gap: 10px;
}

.rail-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: var(--radius-md);
  border: none;
  background: transparent;
  color: var(--fg-secondary);
  cursor: pointer;
  transition: background 0.12s, color 0.12s;
}

.rail-toggle:hover {
  background: var(--surface-elevated);
  color: var(--fg-primary);
}

/* Texto vertical na rail colapsada */
.rail-count-vertical {
  writing-mode: vertical-rl;
  text-orientation: mixed;
  font-size: 10px;
  color: var(--fg-tertiary);
  margin-top: 8px;
  user-select: none;
  letter-spacing: 0.04em;
}

/* Rail expandida */
.rail--expanded {
  width: 268px;
}

/* Cabeçalho */
.rail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px 8px;
  flex-shrink: 0;
}

.rail-title {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--fg-tertiary);
}

.rail-toggle-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: var(--radius-sm);
  border: none;
  background: transparent;
  color: var(--fg-tertiary);
  cursor: pointer;
  transition: background 0.12s, color 0.12s;
}

.rail-toggle-btn:hover {
  background: var(--surface-elevated);
  color: var(--fg-primary);
}

/* Botão nova sessão */
.rail-new {
  padding: 0 10px 8px;
  flex-shrink: 0;
}

/* Campo de busca */
.rail-search {
  padding: 0 10px 8px;
  flex-shrink: 0;
}

/* Lista de sessões */
.sessions-list {
  flex: 1;
  overflow-y: auto;
  list-style: none;
  margin: 0;
  padding: 0 6px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  scrollbar-width: thin;
  scrollbar-color: var(--border) transparent;
}

/* Item da sessão */
.session-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  width: 100%;
  padding: 8px 8px;
  border-radius: var(--radius-md);
  border: none;
  border-left: 2px solid transparent;
  background: transparent;
  cursor: pointer;
  text-align: left;
  transition: background 0.12s, border-color 0.12s;
}

.session-row:hover {
  background: var(--surface-elevated);
}

/* Sessão ativa: borda esquerda brand */
.session-row--active {
  border-left-color: var(--brand-500);
  background: color-mix(in srgb, var(--brand-500) 8%, transparent);
}

.session-icon {
  color: var(--fg-tertiary);
  flex-shrink: 0;
  margin-top: 1px;
}

.session-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.session-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}

.session-title {
  font-size: 12px;
  font-weight: 500;
  color: var(--fg-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  min-width: 0;
}

/* Meta row: ID, data, autor */
.session-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: nowrap;
}

.session-id {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--fg-tertiary);
}

.session-sep {
  color: var(--fg-tertiary);
  font-size: 10px;
}

.session-date,
.session-author {
  font-size: 10px;
  color: var(--fg-tertiary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 70px;
}

/* Estado vazio */
.sessions-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 24px 12px;
  color: var(--fg-tertiary);
  font-size: 12px;
  text-align: center;
}

/* Rodapé */
.rail-footer {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 8px 14px;
  border-top: 1px solid var(--border);
  font-size: 11px;
  color: var(--fg-tertiary);
  flex-shrink: 0;
}
</style>
