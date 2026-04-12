<template>
  <UIcon
    :name="iconName"
    class="inline-block flex-shrink-0 align-middle"
    :style="sizeStyle"
  />
</template>

<script setup lang="ts">
const props = defineProps<{
  channel: "web" | "whatsapp" | "discord" | "telegram" | string
  size?: "xs" | "sm" | "md"
}>()

const iconMap: Record<string, string> = {
  web: "i-heroicons-globe-alt",
  whatsapp: "i-simple-icons-whatsapp",
  discord: "i-simple-icons-discord",
  telegram: "i-simple-icons-telegram",
}

const PX: Record<string, number> = {
  xs: 12,
  sm: 14,
  md: 16,
}

const iconName = computed(() => iconMap[props.channel] || "i-heroicons-chat-bubble-left")
const sizeStyle = computed(() => {
  const px = PX[props.size || "sm"] ?? PX.sm
  return {
    width: `${px}px`,
    height: `${px}px`,
    minWidth: `${px}px`,
    minHeight: `${px}px`,
    fontSize: `${px}px`,
  }
})
</script>
