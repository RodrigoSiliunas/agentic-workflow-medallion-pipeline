<template>
  <button
    :type="type"
    :disabled="disabled"
    :aria-label="label"
    :aria-pressed="active ? 'true' : undefined"
    class="inline-flex items-center justify-center rounded-[var(--radius-md)] transition-colors duration-100 disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:shadow-[var(--shadow-focus)]"
    :class="[sizeClasses, stateClasses]"
  >
    <AppIcon :name="icon" :size="iconSize" />
  </button>
</template>

<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    icon: string
    label: string
    size?: 24 | 28 | 32
    active?: boolean
    disabled?: boolean
    type?: "button" | "submit" | "reset"
  }>(),
  {
    size: 28,
    active: false,
    disabled: false,
    type: "button",
  },
)

const sizeClasses = computed(() => {
  if (props.size === 24) return "w-6 h-6"
  if (props.size === 32) return "w-8 h-8"
  return "w-7 h-7"
})

const iconSize = computed<"xs" | "sm" | "md">(() => {
  if (props.size === 24) return "xs"
  if (props.size === 32) return "md"
  return "sm"
})

const stateClasses = computed(() =>
  props.active
    ? "bg-[var(--surface-elevated)] text-[var(--brand-400)] border border-[rgba(127,34,254,0.3)]"
    : "bg-transparent text-[var(--text-secondary)] border border-transparent hover:bg-[var(--surface-elevated)] hover:text-[var(--text-primary)]",
)
</script>
