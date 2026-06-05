<script setup lang="ts">
import type { EditorChatMessage, SourceOfTruth } from "~/types/pipeline-editor-v2"

// Painel de chat do editor — thread de mensagens + estado zero
const props = withDefaults(defineProps<{
  messages: EditorChatMessage[]
  isStreaming: boolean
  sourceOfTruth?: SourceOfTruth
  showZeroState?: boolean
}>(), {
  sourceOfTruth: null,
  showZeroState: false,
})

const emit = defineEmits<{
  previewProposal: []
  adjustInBuilder: []
  applyProposal: []
  suggestion: [text: string]
}>()

const threadRef = ref<HTMLElement | null>(null)

// Rola para o fim da thread ao receber nova mensagem ou streaming
watch(
  () => [props.messages.length, props.isStreaming] as const,
  async () => {
    await nextTick()
    if (threadRef.value) {
      threadRef.value.scrollTop = threadRef.value.scrollHeight
    }
  }
)
</script>

<template>
  <div class="chat-pane" :class="{ 'chat-pane--chat-source': sourceOfTruth === 'chat' }">
    <!-- Badge flutuante de fonte da verdade (somente quando chat é a fonte) -->
    <div v-if="sourceOfTruth === 'chat'" class="chat-pane__source-badge">
      <span class="chat-pane__source-dot" aria-hidden="true" />
      Fonte da verdade · chat
    </div>

    <!-- Estado zero — preenche e centraliza a coluna -->
    <EditorChatZeroState
      v-if="showZeroState"
      @suggestion="$emit('suggestion', $event)"
    />

    <!-- Thread de mensagens -->
    <div v-else ref="threadRef" class="chat-pane__thread">
      <div class="chat-pane__thread-inner">
        <template v-for="(message, idx) in messages" :key="idx">
          <EditorMessageBubble :message="message" />

          <!-- Card de proposta inline após mensagem do assistente -->
          <ProposalCard
            v-if="message.role === 'assistant' && message.proposal"
            :proposal="message.proposal"
            @preview="emit('previewProposal')"
            @adjust-in-builder="emit('adjustInBuilder')"
            @apply="emit('applyProposal')"
          />
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-pane {
  position: relative;
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

/* Tint sutil quando o chat é a fonte da verdade */
.chat-pane--chat-source {
  background: color-mix(in oklab, var(--brand-600) 1.5%, transparent);
}

/* Badge flutuante "Fonte da verdade · chat" */
.chat-pane__source-badge {
  position: absolute;
  top: 10px;
  left: 16px;
  z-index: 5;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 8px;
  border-radius: 999px;
  background: rgba(142, 81, 246, 0.12);
  border: 1px solid rgba(142, 81, 246, 0.3);
  font-family: var(--font-sans);
  font-size: 10px;
  font-weight: 500;
  color: var(--brand-400);
}

.chat-pane__source-dot {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: var(--brand-500);
  box-shadow: 0 0 0 3px color-mix(in oklab, var(--brand-500) 25%, transparent);
  animation: pulse-soft 1.6s ease-in-out infinite;
  flex-shrink: 0;
}

/* Thread */
.chat-pane__thread {
  flex: 1;
  overflow-y: auto;
  padding: 32px 18px 12px;
  scrollbar-width: thin;
}

.chat-pane__thread-inner {
  max-width: 720px;
  margin: 0 auto;
}
</style>
