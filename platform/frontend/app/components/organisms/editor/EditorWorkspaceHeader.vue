<script setup lang="ts">
import type { SourceOfTruth, SessionStatusV2 } from "~/types/pipeline-editor-v2"

// Props do cabeçalho principal do workspace de edição
withDefaults(defineProps<{
  pipelineName?: string
  layer?: string
  targetNode?: string
  targetTable?: string
  mode?: SourceOfTruth | "chat" | "builder" | "hibrido"
  session: { id: string; status: SessionStatusV2 }
}>(), {
  pipelineName: "Pipeline",
  layer: "silver",
  targetNode: "",
  targetTable: "",
  mode: null,
})

const emit = defineEmits<{
  newSession: []
  share: []
  history: []
  help: []
}>()
</script>

<template>
  <header class="workspace-header">
    <!-- Lado esquerdo: identificação do pipeline e alvo -->
    <div class="header-left">
      <!-- Ícone do pipeline -->
      <div class="pipeline-icon" aria-hidden="true">
        <AppIcon name="cpu-chip" size="sm" />
      </div>

      <div class="header-breadcrumb">
        <!-- Linha 1: pipeline > camada > nó -->
        <div class="breadcrumb-row">
          <span class="pipeline-name">{{ pipelineName }}</span>

          <AppIcon name="chevron-right" size="xs" class="breadcrumb-sep" />

          <AppPill tone="brand" icon="circle-stack" size="xs">
            {{ layer }}
          </AppPill>

          <AppIcon name="chevron-right" size="xs" class="breadcrumb-sep" />

          <AppCode>{{ targetNode }}</AppCode>
        </div>

        <!-- Linha 2: tabela alvo + referência de branch -->
        <div class="breadcrumb-sub">
          <AppIcon name="table-cells" size="xs" />
          <span class="target-table">{{ targetTable }}</span>
          <span class="breadcrumb-dot" aria-hidden="true">·</span>
          <span class="base-ref">base_ref: dev</span>
        </div>
      </div>
    </div>

    <!-- Centro: modo ativo + sessão atual -->
    <div class="header-center">
      <EditorModePill :mode="mode" />
      <EditorSessionPill :id="session.id" :status="session.status" />
    </div>

    <!-- Lado direito: ações globais -->
    <div class="header-right">
      <AppButton
        size="sm"
        variant="outline"
        color="neutral"
        icon="plus"
        @click="emit('newSession')"
      >
        Nova sessão
      </AppButton>

      <AppButton
        size="sm"
        variant="ghost"
        color="neutral"
        icon="share"
        @click="emit('share')"
      >
        Compartilhar
      </AppButton>

      <!-- Separador visual -->
      <div class="header-sep" aria-hidden="true" />

      <AppIconBtn
        icon="clock"
        label="Histórico"
        :size="28"
        @click="emit('history')"
      />

      <AppIconBtn
        icon="question-mark-circle"
        label="Atalhos (?)"
        :size="28"
        @click="emit('help')"
      />
    </div>
  </header>
</template>

<style scoped>
.workspace-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 10px 18px;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
  flex-shrink: 0;
  min-height: 56px;
}

/* Esquerda */
.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
}

.pipeline-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  background: var(--brand-600);
  color: #fff;
  flex-shrink: 0;
}

.header-breadcrumb {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.breadcrumb-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.pipeline-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--fg-primary);
  letter-spacing: -0.015em;
  white-space: nowrap;
}

.breadcrumb-sep {
  color: var(--fg-tertiary);
}

.breadcrumb-sub {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--fg-tertiary);
}

.target-table {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--fg-tertiary);
}

.breadcrumb-dot {
  opacity: 0.4;
}

.base-ref {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--fg-tertiary);
}

/* Centro */
.header-center {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

/* Direita */
.header-right {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.header-sep {
  width: 1px;
  height: 20px;
  background: var(--border);
  margin: 0 2px;
}
</style>
