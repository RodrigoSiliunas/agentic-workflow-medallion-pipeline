<template>
  <div class="flex gap-3" :class="isUser ? 'flex-row-reverse' : ''">
    <!-- Avatar -->
    <UAvatar
      :text="isUser ? 'U' : 'A'"
      size="sm"
      :style="{ background: isUser ? 'var(--brand-primary)' : 'var(--bg-elevated)' }"
    />

    <!-- Bubble -->
    <div
      class="max-w-[75%] px-4 py-3 text-sm"
      :style="{
        background: isUser ? 'var(--brand-primary)' : 'var(--bg-surface)',
        color: isUser ? 'white' : 'var(--text-primary)',
        borderRadius: isUser ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
        border: isUser ? 'none' : '1px solid var(--border-default)',
      }"
    >
      <!-- Markdown content -->
      <div class="prose prose-sm prose-invert max-w-none whitespace-pre-wrap" v-html="renderedContent" />

      <!-- Actions -->
      <div v-if="message.actions?.length" class="mt-2 space-y-1">
        <ActionCard
          v-for="(action, i) in message.actions"
          :key="i"
          :action="action"
        />
      </div>

      <!-- Timestamp + channel -->
      <div class="flex items-center gap-1 mt-1" style="color: var(--text-tertiary)">
        <ChannelIcon v-if="message.channel !== 'web'" :channel="message.channel" size="xs" />
        <span class="text-[10px]">{{ formattedTime }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ChatMessage } from "~/types/chat"

const props = defineProps<{ message: ChatMessage }>()
const isUser = computed(() => props.message.role === "user")

// Renderizar markdown simples (code blocks, bold, links)
const renderedContent = computed(() => {
  let text = props.message.content
  // Code blocks
  text = text.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="bg-[var(--bg-primary)] p-3 rounded-[var(--radius-md)] overflow-x-auto my-2"><code>$2</code></pre>')
  // Inline code
  text = text.replace(/`([^`]+)`/g, '<code class="bg-[var(--bg-primary)] px-1 rounded text-xs">$1</code>')
  // Bold
  text = text.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
  // Links
  text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" class="underline" style="color: var(--brand-primary)">$1</a>')
  return text
})

const formattedTime = computed(() => {
  try {
    return new Date(props.message.timestamp).toLocaleTimeString("pt-BR", {
      hour: "2-digit",
      minute: "2-digit",
    })
  } catch {
    return ""
  }
})
</script>
