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
  <div class="chat-pane">
    <!-- Cabeçalho da seção -->
    <div class="chat-pane__header">
      <AppIcon name="chat-bubble-left-ellipsis" size="xs" />
      <span class="chat-pane__title">Chat</span>
      <div class="chat-pane__spacer" />
      <SourceOfTruthBadge v-if="sourceOfTruth" :source="sourceOfTruth" />
    </div>

    <!-- Área de mensagens -->
    <div ref="threadRef" class="chat-pane__thread">
      <!-- Estado zero -->
      <EditorChatZeroState
        v-if="showZeroState"
        @suggestion="$emit('suggestion', $event)"
      />

      <!-- Thread de mensagens -->
      <template v-else>
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
      </template>
    </div>
  </div>
</template>

<style scoped>
.chat-pane {
  display: flex;
  flex-direction: column;
  height: 100%;
}

/* Cabeçalho */
.chat-pane__header {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
  flex-shrink: 0;
}

.chat-pane__title {
  font-family: var(--font-sans);
  font-size: 11px;
  font-weight: 600;
  color: var(--fg-secondary);
  letter-spacing: 0.03em;
}

.chat-pane__spacer {
  flex: 1;
}

/* Thread */
.chat-pane__thread {
  flex: 1;
  overflow-y: auto;
  padding: 0 18px;
  display: flex;
  flex-direction: column;
  scrollbar-width: thin;
}
</style>
