<template>
  <span class="tooltip-wrap" :data-label="label" :data-position="position">
    <slot />
  </span>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    label: string
    position?: "top" | "bottom" | "left" | "right"
  }>(),
  {
    position: "top",
  },
)
</script>

<style scoped>
.tooltip-wrap {
  position: relative;
  display: inline-flex;
}

.tooltip-wrap::after {
  content: attr(data-label);
  position: absolute;
  font-size: 11px;
  font-weight: 500;
  white-space: nowrap;
  background: var(--text-primary);
  color: var(--bg);
  padding: 4px 8px;
  border-radius: var(--radius-sm);
  pointer-events: none;
  opacity: 0;
  transform: translateY(-2px);
  transition: opacity 120ms ease, transform 120ms ease;
  z-index: 50;
}

.tooltip-wrap[data-position="top"]::after {
  bottom: calc(100% + 6px);
  left: 50%;
  transform: translate(-50%, -2px);
}
.tooltip-wrap[data-position="bottom"]::after {
  top: calc(100% + 6px);
  left: 50%;
  transform: translate(-50%, 2px);
}
.tooltip-wrap[data-position="left"]::after {
  right: calc(100% + 6px);
  top: 50%;
  transform: translate(-2px, -50%);
}
.tooltip-wrap[data-position="right"]::after {
  left: calc(100% + 6px);
  top: 50%;
  transform: translate(2px, -50%);
}

.tooltip-wrap:hover::after,
.tooltip-wrap:focus-within::after {
  opacity: 1;
}

.tooltip-wrap[data-position="top"]:hover::after,
.tooltip-wrap[data-position="top"]:focus-within::after {
  transform: translate(-50%, 0);
}
.tooltip-wrap[data-position="bottom"]:hover::after,
.tooltip-wrap[data-position="bottom"]:focus-within::after {
  transform: translate(-50%, 0);
}
.tooltip-wrap[data-position="left"]:hover::after,
.tooltip-wrap[data-position="left"]:focus-within::after {
  transform: translate(0, -50%);
}
.tooltip-wrap[data-position="right"]:hover::after,
.tooltip-wrap[data-position="right"]:focus-within::after {
  transform: translate(0, -50%);
}
</style>
