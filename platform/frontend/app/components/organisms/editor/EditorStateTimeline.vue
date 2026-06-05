<script setup lang="ts">
import type { StateMachineState } from "~/types/pipeline-editor-v2"

// Definição dos passos da máquina de estados com ícone e rótulo
const STATE_STEPS: Array<{ id: StateMachineState; label: string; icon: string }> = [
  { id: "idle",                label: "Aguardando",       icon: "ellipsis-horizontal-circle" },
  { id: "generating_proposal", label: "Gerando proposta", icon: "sparkles" },
  { id: "running_preview",     label: "Preview",          icon: "play-circle" },
  { id: "validating",          label: "Validando",        icon: "shield-check" },
  { id: "opening_pr",          label: "Abrindo PR",       icon: "code-bracket-square" },
  { id: "pr_created",          label: "PR criado",        icon: "check-circle" },
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

// Mostra animação de pulso quando em progresso
const showPulse = computed(
  () => props.current !== "idle" && props.current !== "pr_created" && !errored.value
)
</script>

<template>
  <div class="state-timeline" role="status" aria-live="polite">
    <!-- Lista de passos -->
    <div class="steps-row">
      <template v-for="(step, idx) in STATE_STEPS" :key="step.id">
        <!-- Passo individual -->
        <div
          class="step"
          :class="[`step--${stepState(idx)}`]"
          :aria-current="idx === currentIdx ? 'step' : undefined"
        >
          <!-- Ícone com possível pulso -->
          <div class="step-icon-wrap">
            <AppIcon :name="step.icon" size="sm" class="step-icon" />
            <!-- Anel de pulso animado no passo atual em progresso -->
            <span v-if="showPulse && idx === currentIdx" class="step-ping" aria-hidden="true" />
          </div>

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
    </div>

    <!-- Mensagem de erro + botão retry -->
    <div v-if="errored && error" class="timeline-error" role="alert">
      <AppIcon name="exclamation-triangle" size="sm" class="error-icon" />
      <span class="error-msg">{{ error }}</span>
      <AppButton
        size="xs"
        variant="outline"
        color="error"
        icon="arrow-path"
        @click="emit('retry')"
      >
        Tentar novamente
      </AppButton>
    </div>
  </div>
</template>

<style scoped>
.state-timeline {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px 16px;
}

/* Linha de passos */
.steps-row {
  display: flex;
  align-items: center;
  gap: 0;
  overflow-x: auto;
  scrollbar-width: none;
}

.steps-row::-webkit-scrollbar {
  display: none;
}

/* Passo base */
.step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 8px 10px;
  border-radius: var(--radius-md);
  min-width: 80px;
  transition: background 0.15s, opacity 0.15s;
  position: relative;
}

.step-icon-wrap {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 1.5px solid transparent;
}

.step-icon {
  position: relative;
  z-index: 1;
}

.step-label {
  font-size: 10px;
  font-weight: 500;
  text-align: center;
  white-space: nowrap;
  line-height: 1.2;
}

.step-duration {
  font-size: 9px;
  font-family: var(--font-mono);
  color: var(--fg-tertiary);
}

/* Estado: passado (concluído) */
.step--past .step-icon-wrap {
  background: color-mix(in srgb, var(--status-success) 12%, transparent);
  border-color: color-mix(in srgb, var(--status-success) 30%, transparent);
}

.step--past .step-icon {
  color: var(--status-success);
}

.step--past .step-label {
  color: var(--status-success);
}

/* Estado: atual (em progresso) */
.step--current .step-icon-wrap {
  background: color-mix(in srgb, var(--brand-500) 15%, transparent);
  border-color: var(--brand-500);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--brand-500) 25%, transparent);
}

.step--current .step-icon {
  color: var(--brand-500);
}

.step--current .step-label {
  color: var(--brand-500);
  font-weight: 600;
}

/* Estado: com erro */
.step--errored .step-icon-wrap {
  background: color-mix(in srgb, var(--status-error) 12%, transparent);
  border-color: var(--status-error);
}

.step--errored .step-icon {
  color: var(--status-error);
}

.step--errored .step-label {
  color: var(--status-error);
  font-weight: 600;
}

/* Estado: pr_created (sucesso final) */
.step--pr_created .step-icon-wrap {
  background: color-mix(in srgb, var(--status-success) 18%, transparent);
  border-color: var(--status-success);
}

.step--pr_created .step-icon {
  color: var(--status-success);
}

.step--pr_created .step-label {
  color: var(--status-success);
  font-weight: 600;
}

/* Estado: futuro */
.step--future {
  opacity: 0.55;
}

.step--future .step-icon-wrap {
  background: var(--surface-elevated);
  border-color: var(--border);
}

.step--future .step-icon {
  color: var(--fg-tertiary);
}

.step--future .step-label {
  color: var(--fg-tertiary);
}

/* Animação de pulso no passo atual */
.step-ping {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: color-mix(in srgb, var(--brand-500) 35%, transparent);
  animation: ping 1.2s cubic-bezier(0, 0, 0.2, 1) infinite;
}

@keyframes ping {
  75%, 100% {
    transform: scale(2);
    opacity: 0;
  }
}

/* Separador entre passos */
.step-sep {
  width: 18px;
  height: 2px;
  background: var(--border);
  flex-shrink: 0;
  border-radius: 1px;
  transition: background 0.2s;
}

.step-sep--done {
  background: var(--status-success);
}

/* Bloco de erro */
.timeline-error {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: var(--radius-md);
  background: color-mix(in srgb, var(--status-error) 8%, transparent);
  border: 1px solid color-mix(in srgb, var(--status-error) 25%, transparent);
}

.error-icon {
  color: var(--status-error);
  flex-shrink: 0;
}

.error-msg {
  flex: 1;
  font-size: 12px;
  color: var(--status-error);
  min-width: 0;
  word-break: break-word;
}
</style>
