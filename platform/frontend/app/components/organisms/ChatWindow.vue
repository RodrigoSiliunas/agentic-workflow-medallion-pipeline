<template>
  <div class="flex-1 flex flex-col overflow-hidden">
    <!-- Messages -->
    <div ref="messagesContainer" class="flex-1 overflow-y-auto p-4 space-y-4">
      <!-- Loading -->
      <div v-if="loading" class="flex justify-center py-8">
        <UIcon name="i-heroicons-arrow-path" class="animate-spin text-2xl" style="color: var(--text-tertiary)" />
      </div>

      <!-- Messages -->
      <MessageBubble v-for="msg in messages" :key="msg.id" :message="msg" />

      <!-- Streaming indicator -->
      <div v-if="isStreaming" class="flex items-center gap-2 px-4 py-2">
        <span class="inline-block w-2 h-2 rounded-full animate-pulse" style="background: var(--brand-primary)" />
        <span class="text-xs" style="color: var(--text-tertiary)">Agente pensando...</span>
      </div>
    </div>

    <!-- Input -->
    <div class="p-4 border-t" style="border-color: var(--border-default)">
      <form class="flex gap-2" @submit.prevent="handleSend">
        <UInput
          v-model="input"
          placeholder="Envie uma mensagem..."
          class="flex-1"
          :disabled="isStreaming"
          @keydown.enter.exact.prevent="handleSend"
        />
        <UButton
          type="submit"
          icon="i-heroicons-paper-airplane"
          :loading="isStreaming"
          :disabled="!input.trim() || isStreaming"
        />
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{ threadId: string }>()

const threadIdRef = toRef(props, "threadId")
const { messages, isStreaming, loading, sendMessage } = useChat(threadIdRef)
const input = ref("")
const messagesContainer = ref<HTMLElement>()

async function handleSend() {
  const text = input.value.trim()
  if (!text || isStreaming.value) return
  input.value = ""
  await sendMessage(text)
}

// Auto-scroll ao receber novas mensagens
watch(
  () => messages.value.length,
  () => {
    nextTick(() => {
      if (messagesContainer.value) {
        messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
      }
    })
  },
)
</script>
