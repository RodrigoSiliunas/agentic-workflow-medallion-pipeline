<template>
  <div class="w-full">
    <label
      v-if="label"
      :for="resolvedId"
      class="block text-xs font-medium mb-1.5"
      :style="{ color: 'var(--text-secondary)' }"
    >
      {{ label }}
    </label>

    <div class="relative">
      <!-- Leading icon -->
      <AppIcon
        v-if="icon"
        :name="normalizedIcon"
        size="sm"
        class="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
        :style="{ color: 'var(--text-tertiary)' }"
      />

      <textarea
        v-if="multiline"
        :id="resolvedId"
        ref="fieldRef"
        :value="modelValue"
        :placeholder="placeholder"
        :disabled="disabled"
        :rows="rows"
        :class="[baseClasses, icon ? 'pl-9' : '', 'resize-none']"
        :style="fieldStyle"
        @input="onInput"
        @keydown="onKeydown"
        @focus="focused = true"
        @blur="focused = false"
      />

      <input
        v-else
        :id="resolvedId"
        ref="fieldRef"
        :value="modelValue"
        :placeholder="placeholder"
        :disabled="disabled"
        :type="type"
        :class="[baseClasses, icon ? 'pl-9' : '']"
        :style="fieldStyle"
        @input="onInput"
        @keydown="onKeydown"
        @focus="focused = true"
        @blur="focused = false"
      >
    </div>

    <p v-if="helper && !error" class="mt-1 text-[11px]" :style="{ color: 'var(--text-tertiary)' }">
      {{ helper }}
    </p>
    <p v-if="error" class="mt-1 text-[11px]" :style="{ color: 'var(--status-error)' }">
      {{ error }}
    </p>
  </div>
</template>

<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    modelValue?: string
    label?: string
    placeholder?: string
    helper?: string
    error?: string
    disabled?: boolean
    multiline?: boolean
    rows?: number
    autoresize?: boolean
    type?: string
    icon?: string
    size?: "xs" | "sm" | "md" | "lg" | "xl"
    id?: string
  }>(),
  {
    modelValue: "",
    disabled: false,
    multiline: false,
    rows: 3,
    autoresize: true,
    type: "text",
    size: "md",
    label: undefined,
    placeholder: undefined,
    helper: undefined,
    error: undefined,
    icon: undefined,
    id: undefined,
  },
)

const emit = defineEmits<{
  "update:modelValue": [value: string]
  keydown: [e: KeyboardEvent]
}>()

const autoId = useId()
const resolvedId = computed(() => props.id ?? autoId)
const focused = ref(false)
const fieldRef = ref<HTMLInputElement | HTMLTextAreaElement | null>(null)

const SIZE_PADDING: Record<string, string> = {
  xs: "px-2.5 py-1 text-xs",
  sm: "px-3 py-1.5 text-xs",
  md: "px-3 py-2 text-sm",
  lg: "px-4 py-2.5 text-base",
  xl: "px-4 py-3 text-base",
}

const baseClasses = computed(() => [
  "w-full rounded-[var(--radius-md)] border font-[var(--font-sans)] transition-colors outline-none",
  "placeholder:opacity-80 disabled:opacity-50 disabled:cursor-not-allowed",
  SIZE_PADDING[props.size] ?? SIZE_PADDING.md,
])

const fieldStyle = computed(() => {
  const hasError = !!props.error
  return {
    background: "var(--surface-elevated)",
    color: "var(--text-primary)",
    borderColor: hasError
      ? "var(--status-error)"
      : focused.value
        ? "var(--brand-500)"
        : "var(--border)",
    boxShadow: focused.value
      ? hasError
        ? "0 0 0 3px rgba(239, 68, 68, 0.15)"
        : "0 0 0 3px rgba(127, 34, 254, 0.18)"
      : "none",
  }
})

const normalizedIcon = computed(() => {
  if (!props.icon) return ""
  // Aceita tanto "i-heroicons-xxx" quanto "xxx" (short form usado pelo AppIcon)
  if (props.icon.startsWith("i-")) return props.icon
  return props.icon
})

function onInput(event: Event) {
  const target = event.target as HTMLInputElement | HTMLTextAreaElement
  emit("update:modelValue", target.value)
  if (props.multiline && props.autoresize) {
    target.style.height = "auto"
    target.style.height = `${Math.min(target.scrollHeight, 240)}px`
  }
}

function onKeydown(event: KeyboardEvent) {
  emit("keydown", event)
}
</script>

<style scoped>
input::placeholder,
textarea::placeholder {
  color: var(--text-tertiary);
}
</style>
