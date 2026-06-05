<template>
  <div
    class="flex gap-2.5 py-2"
    :class="isUser ? 'flex-row-reverse' : 'flex-row'"
  >
    <!-- Avatar -->
    <div class="mt-0.5 flex-shrink-0">
      <AppAvatar v-if="isUser" size="xs" :name="message.author || 'Você'" />
      <SafaLogo v-else variant="icon" :size="26" />
    </div>

    <div class="min-w-0" style="max-width: 85%">
      <!-- Cabeçalho: autor + horário -->
      <div
        class="mb-1 flex items-center gap-1.5"
        :class="isUser ? 'justify-end' : 'justify-start'"
      >
        <span
          class="text-[11px] font-semibold tracking-[-0.005em]"
          :style="{ color: 'var(--fg-secondary)' }"
        >
          {{ isUser ? (message.author || "Você") : "Pipeline agent" }}
        </span>
        <span class="font-mono text-[10px]" :style="{ color: 'var(--fg-tertiary)' }">
          {{ message.time || "agora" }}
        </span>
      </div>

      <!-- Conteúdo da bolha -->
      <div
        v-if="message.content"
        class="text-[13px] leading-[1.55] whitespace-pre-wrap"
        :class="
          isUser
            ? 'rounded-[16px_16px_4px_16px] bg-[var(--brand-600)] px-[13px] py-[10px] text-white'
            : ''
        "
        :style="isUser ? {} : { color: 'var(--fg-primary)' }"
      >
        {{ message.content }}
      </div>

      <!-- Typing dots (streaming) -->
      <div
        v-if="!isUser && message.streaming && !message.content"
        class="mt-1.5 flex items-center gap-1"
      >
        <span
          v-for="i in 3"
          :key="i"
          class="typing-dot"
          :style="{ color: 'var(--brand-500)', animationDelay: `${(i - 1) * 0.15}s` }"
        />
      </div>

      <!-- Slot para proposta inline (ProposalCard — PR-B) -->
      <slot v-if="!isUser" name="proposal" :proposal="message.proposal" />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { EditorChatMessage } from "~/types/pipeline-editor-v2"

const props = defineProps<{
  message: EditorChatMessage
}>()

const isUser = computed(() => props.message.role === "user")
</script>
