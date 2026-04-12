<template>
  <div ref="scrollContainer" class="flex-1 overflow-y-auto">
    <div class="max-w-3xl mx-auto px-4 sm:px-6 py-6">
      <MessageBubble v-for="msg in messages" :key="msg.id" :message="msg" />

      <div
        v-if="isStreaming"
        class="flex items-center gap-2 py-3 pl-10"
        :style="{ color: 'var(--text-tertiary)' }"
      >
        <span
          class="inline-block w-1.5 h-1.5 rounded-full status-pulse"
          :style="{ background: 'var(--brand-500)' }"
        />
        <span class="text-xs">Agente pensando...</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ChatMessage } from "~/types/chat"

const props = defineProps<{
  messages: ChatMessage[]
  isStreaming?: boolean
}>()

const scrollContainer = ref<HTMLElement | null>(null)

function scrollToBottom() {
  nextTick(() => {
    const el = scrollContainer.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

watch(
  () => props.messages.length,
  () => scrollToBottom(),
)

watch(
  () => props.messages.at(-1)?.content,
  () => scrollToBottom(),
)

onMounted(() => scrollToBottom())
</script>
