<template>
  <ol class="flex items-center gap-2">
    <li
      v-for="(step, idx) in steps"
      :key="step.key"
      class="flex items-center gap-2"
      :class="{ 'flex-1': idx < steps.length - 1 }"
    >
      <button
        type="button"
        :disabled="!isReachable(idx)"
        class="flex items-center gap-2 transition-colors"
        :class="{ 'cursor-pointer': isReachable(idx), 'cursor-default': !isReachable(idx) }"
        @click="isReachable(idx) && $emit('select', idx)"
      >
        <span
          class="w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-semibold border transition-all"
          :style="stateStyle(idx)"
        >
          <AppIcon v-if="isDone(idx)" name="check" size="xs" />
          <span v-else>{{ idx + 1 }}</span>
        </span>
        <span
          class="text-xs font-medium tracking-tight hidden sm:inline"
          :style="{
            color: isActive(idx) ? 'var(--text-primary)' : 'var(--text-tertiary)',
          }"
        >
          {{ step.label }}
        </span>
      </button>
      <div
        v-if="idx < steps.length - 1"
        class="flex-1 h-px"
        :style="{
          background: isDone(idx) ? 'var(--brand-500)' : 'var(--border)',
        }"
      />
    </li>
  </ol>
</template>

<script setup lang="ts">
interface Step {
  key: string
  label: string
}

const props = defineProps<{
  steps: Step[]
  current: number
}>()

defineEmits<{ select: [idx: number] }>()

function isActive(idx: number) {
  return idx === props.current
}

function isDone(idx: number) {
  return idx < props.current
}

function isReachable(idx: number) {
  return idx <= props.current
}

function stateStyle(idx: number): Record<string, string> {
  if (isDone(idx)) {
    return {
      background: "var(--brand-600)",
      color: "white",
      borderColor: "var(--brand-600)",
    }
  }
  if (isActive(idx)) {
    return {
      background: "var(--brand-600)",
      color: "white",
      borderColor: "var(--brand-500)",
      boxShadow: "0 0 0 3px rgba(127,34,254,0.25)",
    }
  }
  return {
    background: "var(--surface-elevated)",
    color: "var(--text-tertiary)",
    borderColor: "var(--border)",
  }
}
</script>
