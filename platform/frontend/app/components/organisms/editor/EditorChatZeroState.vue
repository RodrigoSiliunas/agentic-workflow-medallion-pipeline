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
    <!-- Ícone central com glow -->
    <div class="zero-state__icon-box">
      <div class="zero-state__glow" aria-hidden="true" />
      <SafaLogo :size="34" />
    </div>

    <!-- Título principal -->
    <h1 class="zero-state__title">
      Descreva uma mudança na
      <em class="zero-state__title-em">camada Silver</em>
    </h1>

    <!-- Descrição -->
    <p class="zero-state__description">
      Use linguagem natural ou construa visualmente no builder.
      O agente gera uma proposta com até 11 operações DSL que você pode
      revisar, ajustar e aplicar ao rascunho antes de abrir um PR.
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
        Só camada Silver é editável no momento. Gerencie templates em
        <AppCode>/deployments</AppCode>
      </span>
    </div>
  </div>
</template>

<style scoped>
.zero-state {
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
    inset 0 0 18px rgba(142, 81, 246, 0.12);
  flex-shrink: 0;
}

/* Glow radial sobre o ícone */
.zero-state__glow {
  position: absolute;
  inset: -24px;
  border-radius: 50%;
  background: radial-gradient(ellipse at center, rgba(142, 81, 246, 0.18) 0%, transparent 70%);
  pointer-events: none;
  z-index: -1;
}

/* Título */
.zero-state__title {
  font-family: var(--font-sans);
  font-size: 22px;
  font-weight: 600;
  color: var(--fg-primary);
  line-height: 1.25;
  margin: 0;
}

.zero-state__title-em {
  font-style: italic;
  color: var(--brand-400);
  font-size: 28px;
  font-weight: 700;
}

/* Descrição */
.zero-state__description {
  font-family: var(--font-sans);
  font-size: 13px;
  color: var(--fg-secondary);
  line-height: 1.6;
  max-width: 480px;
  margin: 0;
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
  gap: 6px;
  font-family: var(--font-sans);
  font-size: 11px;
  color: var(--fg-tertiary);
}
</style>
