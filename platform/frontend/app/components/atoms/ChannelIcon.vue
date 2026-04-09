<template>
  <UIcon :name="iconName" :class="sizeClass" />
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

const iconName = computed(() => iconMap[props.channel] || "i-heroicons-chat-bubble-left")
const sizeClass = computed(() => ({
  xs: "text-xs",
  sm: "text-sm",
  md: "text-base",
}[props.size || "sm"]))
</script>
