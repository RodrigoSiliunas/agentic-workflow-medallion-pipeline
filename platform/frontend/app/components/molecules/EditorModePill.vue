<template>
  <AppPill :tone="meta.tone" :icon="meta.icon">{{ meta.label }}</AppPill>
</template>

<script setup lang="ts">
type Mode = "chat" | "builder" | "hibrido"

const props = withDefaults(
  defineProps<{ mode?: Mode }>(),
  { mode: "chat" },
)

const MODE_MAP: Record<Mode, { icon: string; label: string; tone: "brand" | "info" }> = {
  chat:    { icon: "chat-bubble-left-right", label: "Chat",    tone: "brand" },
  builder: { icon: "squares-plus",           label: "Builder", tone: "info" },
  hibrido: { icon: "sparkles",               label: "Híbrido", tone: "brand" },
}

const meta = computed(() => MODE_MAP[props.mode] ?? MODE_MAP.chat)
</script>
