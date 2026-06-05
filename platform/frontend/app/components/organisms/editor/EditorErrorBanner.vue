<script setup lang="ts">
// Banner de erro contextual exibido acima do workspace quando há falha de estado
defineProps<{
  error: { title?: string; code?: string; message: string } | null
}>()

const emit = defineEmits<{
  dismiss: []
  retry: []
  details: []
}>()
</script>

<template>
  <div
    v-if="error"
    class="error-banner"
    role="alert"
    aria-live="assertive"
  >
    <!-- Ícone de alerta -->
    <div class="banner-icon" aria-hidden="true">
      <AppIcon name="exclamation-triangle" size="md" />
    </div>

    <!-- Conteúdo do erro -->
    <div class="banner-body">
      <div class="banner-title-row">
        <span v-if="error.title" class="banner-title">{{ error.title }}</span>
        <AppCode v-if="error.code" class="banner-code">{{ error.code }}</AppCode>
      </div>
      <p class="banner-message">{{ error.message }}</p>
    </div>

    <!-- Ações do banner -->
    <div class="banner-actions">
      <AppButton
        size="xs"
        variant="ghost"
        color="error"
        icon="arrow-path"
        @click="emit('retry')"
      >
        Tentar novamente
      </AppButton>

      <AppButton
        size="xs"
        variant="ghost"
        color="neutral"
        icon="document-magnifying-glass"
        @click="emit('details')"
      >
        Detalhes
      </AppButton>

      <AppIconBtn
        icon="x-mark"
        label="Fechar aviso de erro"
        :size="24"
        @click="emit('dismiss')"
      />
    </div>
  </div>
</template>

<style scoped>
.error-banner {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 10px 16px;
  /* Faixa colorida à esquerda */
  border-left: 3px solid var(--status-error);
  border-radius: 0;
  background: color-mix(in srgb, var(--status-error) 10%, transparent);
  /* Sem border-radius para colar nas bordas do contêiner pai */
}

.banner-icon {
  color: var(--status-error);
  flex-shrink: 0;
  margin-top: 1px;
}

.banner-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.banner-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.banner-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--status-error);
  line-height: 1.3;
}

.banner-code {
  font-size: 11px;
}

.banner-message {
  font-size: 12px;
  color: var(--fg-secondary);
  margin: 0;
  line-height: 1.5;
  word-break: break-word;
}

.banner-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}
</style>
