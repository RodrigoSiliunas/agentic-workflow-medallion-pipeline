<script setup lang="ts">
// ---------------------------------------------------------------------------
// Props & emits
// ---------------------------------------------------------------------------
const props = withDefaults(defineProps<{
  steps?: string[]
  currentStep?: number
}>(), {
  steps: () => ["Chat", "Builder", "Preview", "PR"],
  currentStep: 0,
})

const emit = defineEmits<{
  "update:currentStep": [step: number]
}>()

// ---------------------------------------------------------------------------
// Computed helpers
// ---------------------------------------------------------------------------
const hasPrev = computed(() => props.currentStep > 0)
const hasNext = computed(() => props.currentStep < props.steps.length - 1)

function goTo(step: number) {
  emit("update:currentStep", step)
}

function prev() {
  if (hasPrev.value) goTo(props.currentStep - 1)
}

function next() {
  if (hasNext.value) goTo(props.currentStep + 1)
}
</script>

<template>
  <!-- Layout estilo wizard com navegação por etapas -->
  <div class="wizard-layout">
    <!-- Cabeçalho de progresso -->
    <nav class="progress-header" aria-label="Etapas do wizard">
      <template v-for="(step, idx) in steps" :key="idx">
        <!-- Botão de etapa -->
        <button
          class="step-btn"
          :class="{
            active: idx === currentStep,
            done: idx < currentStep
          }"
          :aria-current="idx === currentStep ? 'step' : undefined"
          @click="goTo(idx)"
        >
          <!-- Círculo de índice -->
          <div
            class="step-circle"
            :class="{
              active: idx === currentStep,
              done: idx < currentStep
            }"
          >
            <AppIcon v-if="idx < currentStep" name="check" size="xs" />
            <span v-else>{{ idx + 1 }}</span>
          </div>

          <!-- Rótulo -->
          <span class="step-label">{{ step }}</span>
        </button>

        <!-- Divisor entre etapas -->
        <div
          v-if="idx < steps.length - 1"
          class="step-divider"
          :class="{ done: idx < currentStep }"
        />
      </template>
    </nav>

    <!-- Conteúdo da etapa atual -->
    <div class="step-content">
      <slot />
    </div>

    <!-- Rodapé com navegação prev/next -->
    <div class="wizard-footer">
      <AppButton
        variant="outline"
        color="neutral"
        icon="chevron-left"
        :disabled="!hasPrev"
        @click="prev"
      >
        Anterior
      </AppButton>

      <div class="footer-spacer" />

      <!-- Indicador de posição -->
      <span class="step-indicator">
        {{ currentStep + 1 }} de {{ steps.length }}
      </span>

      <div class="footer-spacer" />

      <AppButton
        variant="solid"
        color="primary"
        trailing-icon="chevron-right"
        :disabled="!hasNext"
        @click="next"
      >
        Próximo
      </AppButton>
    </div>
  </div>
</template>

<style scoped>
/* Layout raiz do wizard */
.wizard-layout {
  display: flex;
  flex-direction: column;
  height: 100%;
}

/* Cabeçalho de progresso */
.progress-header {
  display: flex;
  flex-direction: row;
  gap: 0;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  overflow-x: auto;
}

/* Botão de etapa */
.step-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 18px;
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  color: var(--fg-secondary);
  font-size: 13px;
  font-weight: 500;
  transition: color 0.15s, border-color 0.15s;
  white-space: nowrap;
  flex-shrink: 0;
}

.step-btn:hover {
  color: var(--fg-primary);
  background: color-mix(in srgb, var(--surface-elevated) 60%, transparent);
}

.step-btn.active {
  color: var(--brand-500);
  border-bottom-color: var(--brand-500);
}

.step-btn.done {
  color: var(--fg-primary);
}

/* Círculo de índice */
.step-circle {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
  transition: background 0.15s, color 0.15s;
  background: var(--surface-elevated);
  color: var(--fg-secondary);
  border: 1px solid var(--border);
}

.step-circle.active {
  background: var(--brand-500);
  color: #fff;
  border-color: var(--brand-500);
}

.step-circle.done {
  background: var(--brand-400);
  color: #fff;
  border-color: var(--brand-400);
}

/* Rótulo da etapa */
.step-label {
  line-height: 1;
}

/* Divisor entre etapas */
.step-divider {
  flex: 1;
  height: 1px;
  background: var(--border);
  align-self: center;
  margin: 0 4px;
  transition: background 0.15s;
  min-width: 16px;
}

.step-divider.done {
  background: var(--brand-400);
}

/* Conteúdo da etapa */
.step-content {
  flex: 1;
  overflow: hidden;
}

/* Rodapé do wizard */
.wizard-footer {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  border-top: 1px solid var(--border);
  flex-shrink: 0;
  gap: 8px;
}

.footer-spacer {
  flex: 1;
}

.step-indicator {
  font-size: 12px;
  color: var(--fg-tertiary);
}
</style>
