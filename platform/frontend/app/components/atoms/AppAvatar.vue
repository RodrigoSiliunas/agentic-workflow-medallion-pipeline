<template>
  <UAvatar
    :src="src"
    :alt="alt"
    :size="size"
    :text="initials"
    :ui="{
      root: 'bg-[var(--brand-600)] text-white font-medium rounded-full',
      fallback: 'text-white',
    }"
  />
</template>

<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    src?: string
    alt?: string
    name?: string
    size?: "3xs" | "2xs" | "xs" | "sm" | "md" | "lg" | "xl" | "2xl" | "3xl"
  }>(),
  {
    src: undefined,
    alt: undefined,
    name: undefined,
    size: "sm",
  },
)

const initials = computed(() => {
  if (!props.name) return props.alt?.charAt(0).toUpperCase() ?? "?"
  const parts = props.name.trim().split(/\s+/)
  if (parts.length === 1) return (parts[0]?.charAt(0) ?? "?").toUpperCase()
  return ((parts[0]?.charAt(0) ?? "") + (parts[parts.length - 1]?.charAt(0) ?? "")).toUpperCase()
})
</script>
