<script setup lang="ts">
import type { EditProposal } from "~/types/pipeline-editor-v2"

// Card de proposta gerada pelo agente — exibido inline no chat após a mensagem
const props = defineProps<{
  proposal: EditProposal
}>()

const emit = defineEmits<{
  preview: []
  adjustInBuilder: []
  apply: []
}>()

const opCount = computed(() => props.proposal.draft.operations.length)
</script>

<template>
  <div class="proposal-card">
    <!-- Cabeçalho -->
    <div class="proposal-card__header">
      <div class="proposal-card__header-left">
        <AppIcon name="sparkles" size="xs" style="color: var(--brand-400)" />
        <span class="proposal-card__header-title">Proposta gerada</span>
        <AppPill v-if="proposal.version" tone="brand" size="xs">
          v{{ proposal.version }}
        </AppPill>
      </div>
      <span class="proposal-card__op-count">
        {{ opCount }} {{ opCount === 1 ? "operação" : "operações" }}
      </span>
    </div>

    <!-- Corpo -->
    <div class="proposal-card__body">
      <!-- Coluna principal -->
      <div class="proposal-card__main">
        <!-- Explicação -->
        <p v-if="proposal.explanation" class="proposal-card__explanation">
          {{ proposal.explanation }}
        </p>

        <!-- Lista de operações -->
        <div class="proposal-card__ops">
          <OpMiniRow
            v-for="(op, idx) in proposal.draft.operations"
            :key="idx"
            :op="op"
            :index="idx"
          />
        </div>

        <!-- Arquivos afetados -->
        <div v-if="proposal.files_affected?.length" class="proposal-card__section">
          <span class="proposal-card__overline">Arquivos afetados</span>
          <div class="proposal-card__files">
            <AppCode
              v-for="file in proposal.files_affected"
              :key="file"
              class="proposal-card__file-chip"
            >{{ file }}</AppCode>
          </div>
        </div>

        <!-- Plano de teste -->
        <div v-if="proposal.test_plan?.length" class="proposal-card__section">
          <span class="proposal-card__overline">Plano de teste</span>
          <ul class="proposal-card__test-plan">
            <li
              v-for="(step, idx) in proposal.test_plan"
              :key="idx"
              class="proposal-card__test-item"
            >
              <span class="proposal-card__test-checkbox" aria-hidden="true">
                <AppIcon name="check" :size="9" style="color: var(--brand-400)" />
              </span>
              <span class="proposal-card__test-text">{{ step }}</span>
            </li>
          </ul>
        </div>
      </div>

      <!-- Coluna lateral — risco -->
      <div class="proposal-card__risk">
        <span class="proposal-card__overline">Risco</span>
        <AppRiskGauge :value="proposal.risk_score ?? 0" :size="88" />
      </div>
    </div>

    <!-- Rodapé com ações -->
    <div class="proposal-card__footer">
      <div class="proposal-card__footer-left">
        <AppButton
          variant="ghost"
          size="sm"
          icon="pencil-square"
          @click="emit('adjustInBuilder')"
        >
          Ajustar no builder
        </AppButton>
      </div>
      <div class="proposal-card__footer-right">
        <AppButton
          variant="outline"
          size="sm"
          icon="play"
          @click="emit('preview')"
        >
          Rodar preview
        </AppButton>
        <AppButton
          variant="solid"
          color="primary"
          size="sm"
          icon="check"
          @click="emit('apply')"
        >
          Aplicar ao rascunho
        </AppButton>
      </div>
    </div>
  </div>
</template>

<style scoped>
.proposal-card {
  margin-top: 10px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
  background: var(--surface);
  overflow: hidden;
}

/* Cabeçalho */
.proposal-card__header {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: rgba(142, 81, 246, 0.08);
  border-bottom: 1px solid var(--border);
}

.proposal-card__header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.proposal-card__header-title {
  font-family: var(--font-sans);
  font-size: 12px;
  font-weight: 600;
  color: var(--fg-primary);
}

.proposal-card__op-count {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--fg-tertiary);
}

/* Corpo */
.proposal-card__body {
  display: grid;
  grid-template-columns: 1fr 124px;
}

/* Coluna principal */
.proposal-card__main {
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  border-right: 1px solid var(--border);
}

.proposal-card__explanation {
  font-family: var(--font-sans);
  font-size: 13px;
  color: var(--fg-primary);
  line-height: 1.55;
  margin: 0;
}

.proposal-card__ops {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

/* Seções internas */
.proposal-card__section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.proposal-card__overline {
  font-family: var(--font-sans);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--fg-tertiary);
}

/* Arquivos */
.proposal-card__files {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.proposal-card__file-chip {
  cursor: pointer;
}

/* Plano de teste */
.proposal-card__test-plan {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.proposal-card__test-item {
  display: flex;
  flex-direction: row;
  align-items: flex-start;
  gap: 7px;
}

.proposal-card__test-checkbox {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 12px;
  height: 12px;
  flex-shrink: 0;
  border: 1px solid var(--border);
  border-radius: 3px;
  background: var(--surface-elevated);
  margin-top: 1px;
}

.proposal-card__test-text {
  font-family: var(--font-sans);
  font-size: 12px;
  color: var(--fg-secondary);
  line-height: 1.5;
}

/* Coluna de risco */
.proposal-card__risk {
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  background: rgba(0, 0, 0, 0.015);
}

/* Rodapé */
.proposal-card__footer {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 12px;
  border-top: 1px solid var(--border);
  background: var(--surface-elevated);
}

.proposal-card__footer-left {
  display: flex;
  align-items: center;
  gap: 6px;
}

.proposal-card__footer-right {
  display: flex;
  align-items: center;
  gap: 6px;
}
</style>
