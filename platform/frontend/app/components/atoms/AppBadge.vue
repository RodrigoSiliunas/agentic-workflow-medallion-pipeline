<template>
  <UBadge
    :color="color"
    :variant="variant"
    :size="size"
    :icon="icon"
    :class="[
      'font-medium tracking-tight',
      variant === 'subtle' ? 'border border-[var(--border-subtle)]' : '',
    ]"
  >
    <slot />
  </UBadge>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    color?: "primary" | "neutral" | "error" | "success" | "warning" | "info"
    variant?: "solid" | "outline" | "soft" | "subtle"
    size?: "sm" | "md" | "lg"
    icon?: string
  }>(),
  {
    color: "primary",
    variant: "subtle",
    size: "sm",
    icon: undefined,
  },
)
</script>
