<script setup lang="ts">
// Compositor principal do chat — textarea + controles de microfone e submissão
const props = withDefaults(defineProps<{
  modelValue: string
  disabled?: boolean
  isListening?: boolean
}>(), {
  disabled: false,
  isListening: false
})

const emit = defineEmits<{
  "update:modelValue": [value: string]
  send: []
  toggleListen: []
}>()

const providerId = ref("anthropic")
const modelId = ref("claude-sonnet-4.6")

// Pode submeter apenas se há texto e não está desabilitado
const canSubmit = computed(() => props.modelValue.trim().length > 0 && !props.disabled)

function handleInput(e: Event) {
  emit("update:modelValue", (e.target as HTMLTextAreaElement).value)
}

function handleKeydown(e: KeyboardEvent) {
  // Ctrl+Enter ou Enter sem Shift → enviar
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault()
    if (canSubmit.value) emit("send")
    return
  }
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
    e.preventDefault()
    if (canSubmit.value) emit("send")
  }
}

function handleSend() {
  if (canSubmit.value) emit("send")
}

function handleModelChange(pId: string, mId: string) {
  providerId.value = pId
  modelId.value = mId
}
</script>

<template>
  <div class="composer-wrap">
    <div
      class="composer"
      :class="{ 'composer--listening': isListening }"
    >
    <!-- Strip de ditado por voz -->
    <EditorListeningStrip v-if="isListening" @stop="emit('toggleListen')" />

    <!-- Textarea de entrada -->
    <textarea
      v-else
      class="composer__textarea"
      :value="modelValue"
      :disabled="disabled"
      rows="2"
      placeholder="Descreva uma mudança na camada Silver — ex: renomeie cliente_id para customer_id e remova ssn"
      @input="handleInput"
      @keydown="handleKeydown"
    />

    <!-- Linha de controles inferiores -->
    <div class="composer__controls">
      <!-- Anexo (inerte nesta PR) -->
      <AppButton
        type="button"
        variant="ghost"
        size="sm"
        icon="paper-clip"
        aria-label="Anexar rascunho"
      >
        Anexar rascunho
      </AppButton>

      <!-- Botão de microfone -->
      <button
        class="mic-btn"
        :class="{ 'mic-btn--active': isListening }"
        type="button"
        :aria-label="isListening ? 'Parar de gravar' : 'Ditar por voz'"
        @click="emit('toggleListen')"
      >
        <span v-if="isListening" class="mic-ping" aria-hidden="true" />
        <AppIcon name="microphone" size="sm" />
      </button>

      <div class="composer__spacer" />

      <!-- Seletor de modelo -->
      <EditorModelPicker
        :provider-id="providerId"
        :model-id="modelId"
        @change="handleModelChange"
      />

      <!-- Atalhos de teclado -->
      <div class="composer__kbd-hint" aria-hidden="true">
        <AppKbd>Ctrl</AppKbd>
        <AppKbd>↵</AppKbd>
      </div>

      <!-- Botão enviar -->
      <button
        class="send-btn"
        type="button"
        :disabled="!canSubmit"
        :class="{ 'send-btn--disabled': !canSubmit }"
        aria-label="Enviar mensagem"
        @click="handleSend"
      >
        <AppIcon name="arrow-up" size="sm" style="color: white" />
      </button>
    </div>
    </div>
  </div>
</template>

<style scoped>
.composer-wrap {
  padding: 10px 18px 14px;
  flex-shrink: 0;
}

.composer {
  display: flex;
  flex-direction: column;
  gap: 8px;
  border-radius: var(--radius-xl);
  border: 1px solid var(--border);
  background: var(--surface);
  padding: 10px 12px;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.composer:focus-within {
  border-color: rgba(142, 81, 246, 0.5);
  box-shadow: var(--shadow-focus);
}

.composer--listening {
  border-color: rgba(142, 81, 246, 0.5);
  box-shadow: var(--shadow-focus);
}

/* Textarea */
.composer__textarea {
  resize: none;
  border: none;
  outline: none;
  background: transparent;
  font-family: var(--font-sans);
  font-size: 13px;
  color: var(--fg-primary);
  max-height: 200px;
  min-height: 36px;
  width: 100%;
  line-height: 1.5;
  scrollbar-width: thin;
}

.composer__textarea::placeholder {
  color: var(--fg-tertiary);
}

/* Controles inferiores */
.composer__controls {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 6px;
}

.composer__spacer {
  flex: 1;
}

/* Hint de teclado */
.composer__kbd-hint {
  display: flex;
  align-items: center;
  gap: 3px;
}

/* Botão de microfone */
.mic-btn {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: var(--radius-md);
  border: 1px solid transparent;
  background: transparent;
  cursor: pointer;
  color: var(--fg-secondary);
  transition: background 0.15s, border-color 0.15s;
}

.mic-btn--active {
  border-color: rgba(142, 81, 246, 0.4);
  background: rgba(142, 81, 246, 0.12);
  color: var(--brand-400);
}

.mic-btn:hover:not(.mic-btn--active) {
  background: var(--surface-elevated);
}

/* Animação ping no microfone ativo */
.mic-ping {
  position: absolute;
  inset: 0;
  border-radius: var(--radius-md);
  background: rgba(142, 81, 246, 0.2);
  animation: mic-ping 1.2s ease-out infinite;
}

@keyframes mic-ping {
  0%   { opacity: 0.6; transform: scale(1); }
  100% { opacity: 0;   transform: scale(1.6); }
}

/* Botão enviar */
.send-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: var(--radius-md);
  border: none;
  background: var(--brand-600);
  cursor: pointer;
  transition: opacity 0.15s;
}

.send-btn--disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.send-btn:not(.send-btn--disabled):hover {
  opacity: 0.85;
}
</style>
