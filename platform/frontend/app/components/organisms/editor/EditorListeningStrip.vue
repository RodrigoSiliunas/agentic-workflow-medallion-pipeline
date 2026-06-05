<script setup lang="ts">
// Strip exibida no compositor quando o modo de ditado por voz está ativo
defineEmits<{
  stop: []
}>()
</script>

<template>
  <div class="listening-strip">
    <!-- Barras de equalização animadas -->
    <div class="eq-bars" aria-hidden="true">
      <span
        v-for="i in 12"
        :key="i"
        class="eq-bar"
        :style="{ animationDelay: `${(i - 1) * 0.06}s` }"
      />
    </div>

    <!-- Texto de status -->
    <span class="listening-label">
      Ouvindo…
      <span class="listening-hint">fale a mudança que você quer</span>
    </span>

    <div class="listening-spacer" />

    <!-- Botão parar -->
    <button class="stop-btn" type="button" @click="$emit('stop')">
      <AppIcon name="stop" :size="11" style="color: var(--status-error)" />
      <span>Parar</span>
    </button>
  </div>
</template>

<style scoped>
.listening-strip {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 4px;
  min-height: 36px;
}

/* Barras de equalização */
.eq-bars {
  display: flex;
  align-items: flex-end;
  gap: 2px;
  height: 18px;
}

.eq-bar {
  display: inline-block;
  width: 3px;
  height: 6px;
  background: var(--brand-400);
  border-radius: 2px;
  animation: eq-pulse 0.7s ease-in-out infinite alternate;
}

@keyframes eq-pulse {
  0%   { height: 4px; }
  100% { height: 18px; }
}

/* Texto */
.listening-label {
  font-family: var(--font-sans);
  font-size: 12px;
  font-weight: 600;
  color: var(--fg-primary);
  white-space: nowrap;
}

.listening-hint {
  font-weight: 400;
  color: var(--fg-tertiary);
  margin-left: 4px;
}

.listening-spacer {
  flex: 1;
}

/* Botão parar */
.stop-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
  height: 26px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--surface-elevated);
  cursor: pointer;
  font-family: var(--font-sans);
  font-size: 11px;
  font-weight: 500;
  color: var(--fg-primary);
  transition: background 0.15s;
}

.stop-btn:hover {
  background: var(--surface);
}
</style>
