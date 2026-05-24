<template>
  <component
    :is="tag"
    class="block border bg-[var(--surface)]"
    :class="[paddingClasses, radiusClasses, interactiveClasses]"
    :style="cardStyle"
  >
    <slot />
  </component>
</template>

<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    padding?: "none" | "sm" | "md" | "lg"
    radius?: "md" | "lg" | "xl"
    interactive?: boolean
    glow?: boolean
    tag?: string
  }>(),
  {
    padding: "md",
    radius: "lg",
    interactive: false,
    glow: false,
    tag: "div",
  },
)

const paddingClasses = computed(() => {
  if (props.padding === "none") return ""
  if (props.padding === "sm") return "p-3"
  if (props.padding === "lg") return "p-6"
  return "p-4"
})

const radiusClasses = computed(() => {
  if (props.radius === "md") return "rounded-[var(--radius-md)]"
  if (props.radius === "xl") return "rounded-[var(--radius-xl)]"
  return "rounded-[var(--radius-lg)]"
})

const interactiveClasses = computed(() =>
  props.interactive
    ? "cursor-pointer transition-shadow hover:shadow-[var(--shadow-medium)] focus-visible:outline-none focus-visible:shadow-[var(--shadow-focus)]"
    : "",
)

const cardStyle = computed(() => ({
  borderColor: "var(--border)",
  boxShadow: props.glow
    ? "var(--shadow-card), var(--shadow-inner-glow)"
    : "var(--shadow-card)",
}))
</script>
