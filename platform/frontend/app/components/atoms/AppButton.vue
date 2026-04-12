<template>
  <NuxtLink
    v-if="to"
    :to="to"
    :class="baseClasses"
    :style="variantStyle"
  >
    <!-- Loading spinner -->
    <span
      v-if="loading"
      class="inline-block w-4 h-4 border-2 rounded-full animate-spin"
      :style="{ borderColor: 'currentColor', borderRightColor: 'transparent' }"
    />
    <!-- Leading icon -->
    <AppIcon
      v-else-if="icon"
      :name="icon"
      :size="iconSize"
    />
    <slot v-if="!square" />
    <!-- Trailing icon -->
    <AppIcon
      v-if="trailingIcon && !square"
      :name="trailingIcon"
      :size="iconSize"
    />
  </NuxtLink>

  <button
    v-else
    :type="type"
    :disabled="isDisabled"
    :class="baseClasses"
    :style="variantStyle"
  >
    <span
      v-if="loading"
      class="inline-block w-4 h-4 border-2 rounded-full animate-spin"
      :style="{ borderColor: 'currentColor', borderRightColor: 'transparent' }"
    />
    <AppIcon
      v-else-if="icon"
      :name="icon"
      :size="iconSize"
    />
    <slot v-if="!square" />
    <AppIcon
      v-if="trailingIcon && !square"
      :name="trailingIcon"
      :size="iconSize"
    />
  </button>
</template>

<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    color?: "primary" | "neutral" | "error" | "success" | "warning" | "info"
    variant?: "solid" | "outline" | "soft" | "subtle" | "ghost" | "link"
    size?: "xs" | "sm" | "md" | "lg" | "xl"
    loading?: boolean
    icon?: string
    trailingIcon?: string
    disabled?: boolean
    square?: boolean
    to?: string
    type?: "button" | "submit" | "reset"
    block?: boolean
  }>(),
  {
    color: "primary",
    variant: "solid",
    size: "md",
    loading: false,
    disabled: false,
    square: false,
    icon: undefined,
    trailingIcon: undefined,
    to: undefined,
    type: "button",
    block: false,
  },
)

const isDisabled = computed(() => props.disabled || props.loading)

const SIZE_CLASSES: Record<string, string> = {
  xs: "text-[11px] px-2.5 py-1 rounded-[var(--radius-sm)]",
  sm: "text-xs px-3 py-1.5 rounded-[var(--radius-md)]",
  md: "text-sm px-4 py-2 rounded-[var(--radius-md)]",
  lg: "text-sm px-5 py-2.5 rounded-[var(--radius-md)]",
  xl: "text-base px-6 py-3 rounded-[var(--radius-lg)]",
}

const SQUARE_SIZE: Record<string, string> = {
  xs: "w-6 h-6 p-0",
  sm: "w-8 h-8 p-0",
  md: "w-9 h-9 p-0",
  lg: "w-10 h-10 p-0",
  xl: "w-12 h-12 p-0",
}

const ICON_SIZE: Record<string, "xs" | "sm" | "md" | "lg" | "xl"> = {
  xs: "xs",
  sm: "xs",
  md: "sm",
  lg: "sm",
  xl: "md",
}

const sizeClasses = computed(() => SIZE_CLASSES[props.size] ?? SIZE_CLASSES.md)
const squareSize = computed(() => SQUARE_SIZE[props.size] ?? SQUARE_SIZE.md)
const iconSize = computed(() => ICON_SIZE[props.size] ?? "sm")

const baseClasses = computed(() => [
  "inline-flex items-center justify-center gap-2 font-medium tracking-tight",
  "transition-all duration-150 select-none whitespace-nowrap no-underline cursor-pointer",
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand-500)]/40",
  "disabled:opacity-50 disabled:cursor-not-allowed",
  sizeClasses.value,
  props.square ? squareSize.value : "",
  props.block ? "w-full" : "",
])

const variantStyle = computed(() => {
  const color = props.color
  const variant = props.variant

  const status: Record<string, { bg: string; text: string }> = {
    error: { bg: "var(--status-error)", text: "white" },
    success: { bg: "var(--status-success)", text: "white" },
    warning: { bg: "var(--status-warning)", text: "white" },
    info: { bg: "var(--status-info)", text: "white" },
  }

  if (variant === "solid") {
    if (color === "primary") {
      return {
        background: "var(--brand-600)",
        color: "white",
        border: "1px solid transparent",
        boxShadow: "var(--shadow-subtle)",
      }
    }
    if (color === "neutral") {
      return {
        background: "var(--surface-elevated)",
        color: "var(--text-primary)",
        border: "1px solid var(--border)",
      }
    }
    if (status[color]) {
      return {
        background: status[color]!.bg,
        color: status[color]!.text,
        border: "1px solid transparent",
      }
    }
  }

  if (variant === "outline") {
    if (color === "primary") {
      return {
        background: "transparent",
        color: "var(--brand-400)",
        border: "1px solid var(--brand-500)",
      }
    }
    return {
      background: "transparent",
      color: "var(--text-primary)",
      border: "1px solid var(--border)",
    }
  }

  if (variant === "soft" || variant === "subtle") {
    if (color === "primary") {
      return {
        background: "rgba(127, 34, 254, 0.12)",
        color: "var(--brand-400)",
        border: variant === "subtle" ? "1px solid rgba(127,34,254,0.3)" : "1px solid transparent",
      }
    }
    return {
      background: "var(--surface-elevated)",
      color: "var(--text-secondary)",
      border: variant === "subtle" ? "1px solid var(--border)" : "1px solid transparent",
    }
  }

  if (variant === "ghost") {
    return {
      background: "transparent",
      color: "var(--text-secondary)",
      border: "1px solid transparent",
    }
  }

  if (variant === "link") {
    return {
      background: "transparent",
      color: "var(--brand-400)",
      border: "1px solid transparent",
      padding: "0",
      textDecoration: "underline",
    }
  }

  return {}
})
</script>

<style scoped>
button:hover:not(:disabled),
a:hover {
  filter: brightness(1.1);
}

button:active:not(:disabled),
a:active {
  filter: brightness(0.95);
}
</style>
