<script setup lang="ts">
import type { PipelineEditSession } from "~/types/pipeline-editor-v2"

// Modal de confirmação de reversão de alteração do pipeline editor
defineProps<{
  open: boolean
  session: PipelineEditSession
}>()

const emit = defineEmits<{
  close: []
  confirm: [mode: "revert_pr" | "close_pr" | "draft"]
}>()

// Modo de reversão selecionado
const mode = ref<"revert_pr" | "close_pr" | "draft">("revert_pr")

// Opções de reversão disponíveis
const options: Array<{
  id: "revert_pr" | "close_pr" | "draft"
  icon: string
  title: string
  description: string
}> = [
  {
    id: "revert_pr",
    icon: "arrow-uturn-left",
    title: "Reverter PR",
    description: "Fecha o pull request aberto e reverte o branch para o estado anterior."
  },
  {
    id: "close_pr",
    icon: "x-circle",
    title: "Fechar PR sem reverter",
    description: "Fecha o pull request mas mantém as alterações no rascunho da sessão."
  },
  {
    id: "draft",
    icon: "document-text",
    title: "Voltar para rascunho",
    description: "Descarta o PR e volta a sessão para o modo de rascunho para edição."
  }
]
</script>

<template>
  <EditorModalShell
    :open="open"
    title="Reverter alteração"
    icon="arrow-uturn-left"
    icon-tone="warning"
    :width="520"
    @close="emit('close')"
  >
    <!-- Corpo do modal de reversão -->
    <div class="revert-body">
      <!-- Texto explicativo -->
      <p class="revert-desc">
        Escolha como deseja reverter as alterações da sessão
        <AppCode>{{ session.id }}</AppCode>. Esta ação não pode ser desfeita.
      </p>

      <!-- Opções de modo de reversão -->
      <div class="revert-options">
        <button
          v-for="opt in options"
          :key="opt.id"
          class="revert-option"
          :class="{ 'revert-option--selected': mode === opt.id }"
          type="button"
          @click="mode = opt.id"
        >
          <!-- Rádio customizado -->
          <span class="option-radio">
            <span v-if="mode === opt.id" class="option-radio-dot" />
          </span>

          <!-- Ícone da opção -->
          <span class="option-icon-box">
            <AppIcon :name="opt.icon" size="sm" class="option-icon" />
          </span>

          <!-- Textos da opção -->
          <span class="option-text">
            <span class="option-title">{{ opt.title }}</span>
            <span class="option-description">{{ opt.description }}</span>
          </span>
        </button>
      </div>

      <!-- Código do modo selecionado -->
      <div class="revert-selected-mode">
        <span class="selected-label">Modo selecionado:</span>
        <AppCode>{{ mode }}</AppCode>
      </div>
    </div>

    <!-- Rodapé com ações -->
    <template #footer>
      <div class="revert-footer">
        <AppButton variant="ghost" color="neutral" size="sm" @click="emit('close')">
          Cancelar
        </AppButton>
        <AppButton
          variant="solid"
          color="error"
          size="sm"
          icon="arrow-uturn-left"
          @click="emit('confirm', mode)"
        >
          Confirmar reversão
        </AppButton>
      </div>
    </template>
  </EditorModalShell>
</template>

<style scoped>
/* Corpo principal */
.revert-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Texto descritivo */
.revert-desc {
  font-size: 14px;
  color: var(--fg-secondary);
  line-height: 1.6;
  margin: 0;
}

/* Lista de opções de reversão */
.revert-options {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* Botão de opção de reversão */
.revert-option {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 14px;
  background: var(--surface-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  cursor: pointer;
  text-align: left;
  transition: border-color 120ms ease, background 120ms ease;
  width: 100%;
}

.revert-option:hover {
  background: var(--bg);
  border-color: var(--fg-tertiary);
}

/* Estado selecionado */
.revert-option--selected {
  border-color: var(--status-warning);
  background: rgba(245, 158, 11, 0.05);
}

/* Círculo de rádio */
.option-radio {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 2px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 2px;
  transition: border-color 120ms ease;
}

.revert-option--selected .option-radio {
  border-color: var(--status-warning);
}

.option-radio-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--status-warning);
}

/* Ícone da opção */
.option-icon-box {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  background: var(--bg);
  border: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.option-icon {
  color: var(--fg-secondary);
}

.revert-option--selected .option-icon {
  color: var(--status-warning);
}

/* Textos */
.option-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.option-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--fg-primary);
  display: block;
}

.option-description {
  font-size: 13px;
  color: var(--fg-secondary);
  line-height: 1.5;
  display: block;
}

/* Modo selecionado em destaque */
.revert-selected-mode {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: var(--surface-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.selected-label {
  font-size: 12px;
  color: var(--fg-tertiary);
}

/* Rodapé */
.revert-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
