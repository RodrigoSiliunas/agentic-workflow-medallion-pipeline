<script setup lang="ts">
// Estado zero do chat — exibido antes de qualquer mensagem ser enviada
const emit = defineEmits<{
  suggestion: [text: string]
}>()

// Exemplos de sugestões de mudança
const examples = [
  {
    icon: "arrows-right-left",
    title: "renomeie cliente_id para customer_id",
    hint: "rename_column"
  },
  {
    icon: "eye-slash",
    title: "mascare a coluna ssn como PII",
    hint: "mask_pii"
  },
  {
    icon: "funnel",
    title: "filtre linhas com status='cancelled'",
    hint: "filter_rows"
  }
]
</script>

<template>
  <div class="zero-state">
    <!-- Ícone central com glow (apenas o spark, sem wordmark) -->
    <div class="zero-state__icon-box">
      <div class="zero-state__glow" aria-hidden="true" />
      <SafaLogo variant="icon" :size="34" />
    </div>

    <!-- Título principal -->
    <h1 class="zero-state__title">
      Descreva uma mudança na&nbsp;<em class="zero-state__title-em">camada Silver</em>
    </h1>

    <!-- Descrição -->
    <p class="zero-state__description">
      Conte em linguagem natural o que você quer mudar — ou monte direto no
      <strong class="zero-state__description-strong">builder low-code</strong> ao lado.
      As 11 operações DSL cobrem desde renomear coluna até mascarar PII.
    </p>

    <!-- Cards de exemplo -->
    <div class="zero-state__examples">
      <ZeroStateExampleCard
        v-for="ex in examples"
        :key="ex.hint"
        :icon="ex.icon"
        :title="ex.title"
        :hint="ex.hint"
        @click="emit('suggestion', ex.title)"
      />
    </div>

    <!-- Info disclaimer -->
    <div class="zero-state__info">
      <AppIcon name="information-circle" size="xs" />
      <span>
        Só camada Silver é suportada nesta release. Bronze/Gold continuam em
        <AppCode>/deployments</AppCode>
      </span>
    </div>
  </div>
</template>

<style scoped>
.zero-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px 48px 48px;
  text-align: center;
  gap: 18px;
}

/* Caixa de ícone com glow */
.zero-state__icon-box {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 64px;
  height: 64px;
  border-radius: var(--radius-xl);
  background: var(--surface);
  border: 1px solid rgba(142, 81, 246, 0.35);
  box-shadow:
    var(--shadow-focus),
    inset 0 0 40px rgba(127, 34, 254, 0.18);
  flex-shrink: 0;
}

/* Glow radial sobre o ícone */
.zero-state__glow {
  position: absolute;
  inset: -10px;
  border-radius: calc(var(--radius-xl) + 10px);
  background: radial-gradient(circle at center, rgba(127, 34, 254, 0.25), transparent 60%);
  pointer-events: none;
}

/* Título */
.zero-state__title {
  font-family: var(--font-sans);
  font-size: 24px;
  font-weight: 600;
  color: var(--fg-primary);
  letter-spacing: -0.025em;
  line-height: 1.2;
  /* O texto cabe em ~447px (< 520px), mas o text-wrap:balance com a fonte
     fallback quebrava o heading em 2 linhas. Mantém em uma linha como no
     protótipo (que usa Geist real). */
  max-width: 520px;
  white-space: nowrap;
  margin: 0;
}

.zero-state__title-em {
  font-family: var(--font-display);
  font-style: italic;
  font-weight: 400;
  font-size: 28px;
  line-height: 1;
  color: var(--brand-400);
  letter-spacing: -0.03em;
  vertical-align: baseline;
  white-space: nowrap;
}

/* Descrição */
.zero-state__description {
  font-family: var(--font-sans);
  font-size: 13px;
  color: var(--fg-tertiary);
  line-height: 1.6;
  max-width: 460px;
  margin: 0;
}

.zero-state__description-strong {
  font-weight: 600;
  color: var(--fg-secondary);
}

/* Grid de exemplos */
.zero-state__examples {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  max-width: 640px;
  width: 100%;
}

/* Info */
.zero-state__info {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-sans);
  font-size: 11px;
  color: var(--fg-tertiary);
}
</style>
