<template>
  <LandingCardShell
    eyebrow="Chat multi-canal"
    title="WhatsApp. Discord. Telegram."
    description="Mesma conversa, qualquer canal. Slash commands e streaming em todos."
  >
    <div class="px-6 pb-6">
      <!-- Stack de bolhas de conversa com ChannelIcon -->
      <div class="space-y-2">
        <div
          v-for="msg in messages"
          :key="msg.id"
          class="flex gap-2 items-start"
          :class="msg.role === 'user' ? 'flex-row-reverse' : ''"
        >
          <!-- Avatar com ChannelIcon pros user msgs -->
          <div
            class="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0"
            :style="{ background: msg.role === 'user' ? channelBg(msg.channel) : 'var(--surface-elevated)' }"
          >
            <ChannelIcon
              v-if="msg.role === 'user'"
              :channel="msg.channel"
              size="xs"
              class="text-white"
            />
            <svg v-else viewBox="0 0 20 20" fill="var(--brand-500)" class="w-3.5 h-3.5">
              <path fill-rule="evenodd" d="M5 2a1 1 0 011 1v1h1a1 1 0 010 2H6v1a1 1 0 01-2 0V6H3a1 1 0 010-2h1V3a1 1 0 011-1zm0 10a1 1 0 011 1v1h1a1 1 0 110 2H6v1a1 1 0 11-2 0v-1H3a1 1 0 110-2h1v-1a1 1 0 011-1zM12 2a1 1 0 01.967.744L14.146 7.2 17.5 9.134a1 1 0 010 1.732l-3.354 1.935-1.18 4.455a1 1 0 01-1.933 0L9.854 12.8 6.5 10.866a1 1 0 010-1.732l3.354-1.935 1.18-4.455A1 1 0 0112 2z" clip-rule="evenodd" />
            </svg>
          </div>

          <!-- Bubble -->
          <div
            class="max-w-[80%] rounded-[var(--radius-md)] px-3 py-1.5 text-[11px] leading-snug"
            :style="bubbleStyle(msg)"
          >
            {{ msg.content }}
          </div>
        </div>
      </div>

      <!-- Channel legend -->
      <div
        class="mt-4 pt-3 border-t flex items-center justify-around text-[10px]"
        :style="{ borderColor: 'var(--border)', color: 'var(--text-tertiary)' }"
      >
        <div class="flex items-center gap-1.5">
          <div class="w-3 h-3 rounded-full flex items-center justify-center" :style="{ background: '#25d366' }">
            <ChannelIcon channel="whatsapp" size="xs" class="text-white" />
          </div>
          <span>WhatsApp</span>
        </div>
        <div class="flex items-center gap-1.5">
          <div class="w-3 h-3 rounded-full flex items-center justify-center" :style="{ background: '#5865f2' }">
            <ChannelIcon channel="discord" size="xs" class="text-white" />
          </div>
          <span>Discord</span>
        </div>
        <div class="flex items-center gap-1.5">
          <div class="w-3 h-3 rounded-full flex items-center justify-center" :style="{ background: '#229ed9' }">
            <ChannelIcon channel="telegram" size="xs" class="text-white" />
          </div>
          <span>Telegram</span>
        </div>
      </div>
    </div>
  </LandingCardShell>
</template>

<script setup lang="ts">
interface Msg {
  id: string
  role: "user" | "assistant"
  channel: "whatsapp" | "discord" | "telegram"
  content: string
}

const messages: Msg[] = [
  { id: "1", role: "user", channel: "whatsapp", content: "/status bronze" },
  { id: "2", role: "assistant", channel: "whatsapp", content: "SUCCESS às 15:18, 153k linhas" },
  { id: "3", role: "user", channel: "discord", content: "PR #15 já mergeou?" },
  { id: "4", role: "assistant", channel: "discord", content: "Sim, rodou novamente OK." },
]

const CHANNEL_BG: Record<string, string> = {
  whatsapp: "#25d366",
  discord: "#5865f2",
  telegram: "#229ed9",
}

function channelBg(channel: string): string {
  return CHANNEL_BG[channel] ?? "var(--brand-600)"
}

function bubbleStyle(msg: Msg): Record<string, string> {
  if (msg.role === "user") {
    return {
      background: channelBg(msg.channel),
      color: "white",
    }
  }
  return {
    background: "var(--surface-elevated)",
    color: "var(--text-secondary)",
    border: "1px solid var(--border)",
  }
}
</script>
