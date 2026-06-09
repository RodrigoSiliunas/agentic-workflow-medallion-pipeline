<script setup lang="ts">
import type { StateMachineState } from "~/types/pipeline-editor-v2"

// Definição dos passos da máquina de estados com ícone e rótulo (paridade c/ protótipo RF-07)
const STATE_STEPS: Array<{ id: StateMachineState; label: string; icon: string }> = [
  { id: "idle",                label: "Rascunho",         icon: "pencil-square" },
  { id: "generating_proposal", label: "Gerando proposta", icon: "sparkles" },
  { id: "running_preview",     label: "Preview Databricks", icon: "play" },
  { id: "validating",          label: "Validando",        icon: "shield-check" },
  { id: "opening_pr",          label: "Abrindo PR",       icon: "code-bracket" },
  { id: "pr_created",          label: "PR aberto",        icon: "check-circle" },
]

const props = withDefaults(defineProps<{
  current?: StateMachineState
  error?: string | null
  durationMs?: number | null
}>(), {
  current: "idle",
  error: null,
  durationMs: null,
})

const emit = defineEmits<{
  retry: []
}>()

// Índice do estado atual na lista de passos
const currentIdx = computed(() =>
  STATE_STEPS.findIndex((s) => s.id === props.current)
)

// Estado de erro: há mensagem de erro e não estamos em idle/pr_created
const errored = computed(() => !!props.error && props.current !== "idle" && props.current !== "pr_created")

// Duração formatada em segundos
const durationLabel = computed(() => {
  if (props.durationMs == null) return null
  return `${(props.durationMs / 1000).toFixed(1)}s`
})

// Calcula o estado visual de cada passo
function stepState(idx: number) {
  if (errored.value && idx === currentIdx.value) return "errored"
  if (props.current === "pr_created" && idx === STATE_STEPS.length - 1) return "pr_created"
  if (idx < currentIdx.value) return "past"
  if (idx === currentIdx.value) return "current"
  return "future"
}

// Ícone exibido: check em passos concluídos, alerta no passo com erro
function stepIcon(idx: number) {
  const state = stepState(idx)
  if (state === "errored") return "exclamation-triangle"
  if (state === "past") return "check"
  return STATE_STEPS[idx].icon
}

// Mostra animação de pulso quando em progresso
const showPulse = computed(
  () => props.current !== "idle" && props.current !== "pr_created" && !errored.value
)
</script>

<template>
  <div class="state-timeline" role="status" aria-live="polite">
    <template v-for="(step, idx) in STATE_STEPS" :key="step.id">
      <!-- Passo individual (pill horizontal) -->
      <div
        class="step"
        :class="[`step--${stepState(idx)}`]"
        :aria-current="idx === currentIdx ? 'step' : undefined"
      >
        <!-- Ícone com possível pulso -->
        <span class="step-icon-wrap">
          <span v-if="showPulse && idx === currentIdx" class="step-ping" aria-hidden="true" />
          <AppIcon :name="stepIcon(idx)" size="xs" class="step-icon" />
        </span>

        <span class="step-label">{{ step.label }}</span>

        <!-- Duração no passo atual -->
        <span v-if="idx === currentIdx && durationLabel" class="step-duration">
          {{ durationLabel }}
        </span>
      </div>

      <!-- Separador entre passos -->
      <div
        v-if="idx < STATE_STEPS.length - 1"
        class="step-sep"
        :class="{ 'step-sep--done': stepState(idx) === 'past' || stepState(idx) === 'pr_created' }"
        aria-hidden="true"
      />
    </template>

    <!-- Mensagem de erro + botão retry -->
    <div v-if="errored && error" class="timeline-error" role="alert">
      <span class="error-msg">{{ error }}</span>
      <AppButton
        size="xs"
        variant="soft"
        color="error"
        icon="arrow-path"
        @click="emit('retry')"
      >
        Tentar de novo
      </AppButton>
    </div>
  </div>
</template>

<style scoped>
/* Linha de passos — pills horizontais (paridade c/ protótipo RF-07) */
.state-timeline {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 18px;
  border-bottom: 1px solid var(--border);
  background: var(--bg);
  flex-shrink: 0;
  overflow-x: auto;
  scrollbar-width: none;
}

.state-timeline::-webkit-scrollbar {
  display: none;
}

/* Passo base (pill) */
.step {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 5px 11px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: transparent;
  font-family: var(--font-sans);
  font-size: 11px;
  font-weight: 500;
  color: var(--fg-tertiary);
  letter-spacing: -0.005em;
  white-space: nowrap;
  transition: all 0.2s ease;
}

.step-icon-wrap {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
}

.step-icon {
  position: relative;
  z-index: 1;
  color: var(--fg-tertiary);
}

.step-label {
  line-height: 1.2;
}

.step-duration {
  font-size: 10px;
  font-family: var(--font-mono);
  color: var(--fg-tertiary);
}

/* Estado: passado (concluído) */
.step--past {
  background: color-mix(in oklab, var(--status-success) 10%, transparent);
  border-color: color-mix(in oklab, var(--status-success) 30%, transparent);
  color: var(--fg-secondary);
}

.step--past .step-icon {
  color: var(--status-success);
}

/* Estado: atual (em progresso) */
.step--current {
  background: rgba(142, 81, 246, 0.1);
  border-color: rgba(142, 81, 246, 0.4);
  color: var(--fg-primary);
}

.step--current .step-icon {
  color: var(--brand-400);
}

/* Estado: com erro */
.step--errored {
  background: color-mix(in oklab, var(--status-error) 12%, transparent);
  border-color: color-mix(in oklab, var(--status-error) 40%, transparent);
  color: var(--status-error);
}

.step--errored .step-icon {
  color: var(--status-error);
}

/* Estado: pr_created (sucesso final) */
.step--pr_created {
  background: color-mix(in oklab, var(--status-success) 14%, transparent);
  border-color: color-mix(in oklab, var(--status-success) 40%, transparent);
  color: var(--status-success);
}

.step--pr_created .step-icon {
  color: var(--status-success);
}

/* Estado: futuro */
.step--future {
  opacity: 0.55;
}

.step--future .step-icon {
  color: var(--fg-tertiary);
}

/* Animação de pulso no passo atual */
.step-ping {
  position: absolute;
  inset: -3px;
  border-radius: 999px;
  background: rgba(142, 81, 246, 0.35);
  animation: ping 1.6s ease-out infinite;
}

/* Separador entre passos */
.step-sep {
  width: 18px;
  height: 1px;
  background: var(--border);
  flex-shrink: 0;
  transition: background 0.2s;
}

.step-sep--done {
  background: color-mix(in oklab, var(--status-success) 40%, transparent);
}

/* Bloco de erro inline */
.timeline-error {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: 8px;
}

.error-msg {
  font-family: var(--font-sans);
  font-size: 11px;
  color: var(--status-error);
  min-width: 0;
  white-space: nowrap;
}
</style>
