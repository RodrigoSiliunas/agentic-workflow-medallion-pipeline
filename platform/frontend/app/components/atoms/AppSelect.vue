<template>
  <select
    class="outline-none cursor-pointer"
    :style="selectStyle"
    :value="modelValue"
    :disabled="disabled"
    @change="emit('update:modelValue', ($event.target as HTMLSelectElement).value)"
  >
    <option v-for="opt in options" :key="opt.value" :value="opt.value">
      {{ opt.label }}
    </option>
  </select>
</template>

<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    modelValue?: string
    options: { value: string; label: string }[]
    size?: "sm" | "md"
    disabled?: boolean
  }>(),
  {
    modelValue: undefined,
    size: "sm",
    disabled: false,
  },
)

const emit = defineEmits<{
  "update:modelValue": [value: string]
}>()

// SVG inline do chevron (sem dependência de IconBtn)
const CHEVRON_SVG =
  "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6' fill='none'><path d='M1 1l4 4 4-4' stroke='%23A1A1AA' stroke-width='1.4' stroke-linecap='round'/></svg>\")"

const selectStyle = computed(() => ({
  appearance: "none" as const,
  WebkitAppearance: "none" as const,
  height: props.size === "sm" ? "28px" : "34px",
  padding: "0 28px 0 10px",
  borderRadius: "var(--radius-md)",
  border: "1px solid var(--border)",
  backgroundColor: "var(--surface-elevated)",
  backgroundImage: CHEVRON_SVG,
  backgroundRepeat: "no-repeat",
  backgroundPosition: "right 10px center",
  color: "var(--fg-primary)",
  fontFamily: "var(--font-sans)",
  fontSize: props.size === "sm" ? "12px" : "13px",
  opacity: props.disabled ? "0.5" : "1",
  cursor: props.disabled ? "not-allowed" : "pointer",
}))
</script>
