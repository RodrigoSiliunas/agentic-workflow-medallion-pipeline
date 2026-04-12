<template>
  <div class="flex gap-3 py-3" :class="isUser ? 'justify-end' : 'justify-start'">
    <div v-if="!isUser" class="flex-shrink-0 mt-0.5">
      <SafaLogo variant="icon" :size="28" />
    </div>

    <div
      class="max-w-[80%] text-sm leading-relaxed"
      :class="[
        isUser
          ? 'px-4 py-2.5 rounded-[var(--radius-lg)] rounded-br-[var(--radius-sm)] bg-[var(--brand-600)] text-white'
          : 'text-[var(--text-primary)]',
      ]"
    >
      <!-- eslint-disable-next-line vue/no-v-html -- conteudo e sanitizado via escapeHtml antes de aplicar markdown whitelist -->
      <div class="prose prose-sm prose-invert max-w-none whitespace-pre-wrap" v-html="renderedContent" />

      <div v-if="message.actions?.length" class="mt-2 space-y-1.5 not-prose">
        <ActionCard v-for="(action, i) in message.actions" :key="i" :action="action" />
      </div>

      <div
        v-if="formattedTime"
        class="flex items-center gap-1.5 mt-1.5"
        :class="isUser ? 'justify-end' : 'justify-start'"
      >
        <ChannelIcon
          v-if="message.channel !== 'web'"
          :channel="message.channel"
          size="xs"
        />
        <span
          class="text-[10px] tabular-nums"
          :style="{ color: isUser ? 'rgba(255,255,255,0.7)' : 'var(--text-tertiary)' }"
        >
          {{ formattedTime }}
        </span>
      </div>
    </div>

    <div v-if="isUser" class="flex-shrink-0 mt-0.5">
      <AppAvatar size="xs" name="Rodrigo" />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ChatMessage } from "~/types/chat"

const props = defineProps<{ message: ChatMessage }>()
const isUser = computed(() => props.message.role === "user")

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;")
}

const renderedContent = computed(() => {
  if (isUser.value) return escapeHtml(props.message.content)

  let text = escapeHtml(props.message.content)
  // Code blocks (antes de inline pra nao conflitar)
  text = text.replace(
    /```(\w*)\n([\s\S]*?)```/g,
    '<pre class="bg-[var(--surface-elevated)] border border-[var(--border)] p-3 rounded-[var(--radius-md)] overflow-x-auto my-2 text-xs"><code>$2</code></pre>',
  )
  // Inline code
  text = text.replace(
    /`([^`]+)`/g,
    '<code class="bg-[var(--surface-elevated)] border border-[var(--border)] px-1 py-0.5 rounded text-[11px]">$1</code>',
  )
  // Headers (#### → h5, ### → h4, ## → h3) — ordem do mais especifico pro generico
  text = text.replace(
    /^#{4,} (.+)$/gm,
    '<h5 class="text-xs font-semibold mt-3 mb-1" style="color: var(--text-primary)">$1</h5>',
  )
  text = text.replace(
    /^### (.+)$/gm,
    '<h4 class="text-sm font-semibold mt-3 mb-1" style="color: var(--text-primary)">$1</h4>',
  )
  text = text.replace(
    /^## (.+)$/gm,
    '<h3 class="text-base font-semibold mt-3 mb-1" style="color: var(--text-primary)">$1</h3>',
  )
  // Horizontal rule (---)
  text = text.replace(
    /^-{3,}$/gm,
    '<hr class="border-t border-[var(--border)] my-3" />',
  )
  // Bold
  text = text.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
  // Italic (single *)
  text = text.replace(/\*([^*]+)\*/g, "<em>$1</em>")
  // Links
  text = text.replace(
    /\[([^\]]+)\]\(([^)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener" class="underline text-[var(--brand-500)]">$1</a>',
  )
  // Tables (| col1 | col2 | ... |)
  text = text.replace(
    /^(\|.+\|)\n\|[-| :]+\|\n((?:\|.+\|\n?)+)/gm,
    (_match, header, body) => {
      const ths = header.split("|").filter(Boolean).map(
        (c: string) => `<th class="px-2 py-1 text-left text-[10px] font-semibold" style="color:var(--text-tertiary)">${c.trim()}</th>`
      ).join("")
      const rows = body.trim().split("\n").map((row: string) => {
        const tds = row.split("|").filter(Boolean).map(
          (c: string) => `<td class="px-2 py-1 text-[11px] border-t border-[var(--border)]">${c.trim()}</td>`
        ).join("")
        return `<tr>${tds}</tr>`
      }).join("")
      return `<table class="w-full border border-[var(--border)] rounded-[var(--radius-md)] overflow-hidden my-2"><thead><tr>${ths}</tr></thead><tbody>${rows}</tbody></table>`
    },
  )
  // Lists (- item)
  text = text.replace(
    /^- (.+)$/gm,
    '<li class="ml-4 list-disc">$1</li>',
  )
  // Numbered lists (1. item)
  text = text.replace(
    /^\d+\. (.+)$/gm,
    '<li class="ml-4 list-decimal">$1</li>',
  )
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
