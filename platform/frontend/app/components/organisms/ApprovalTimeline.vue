<template>
  <section class="rounded-lg border p-4 space-y-3" :style="{ borderColor: 'var(--border)' }">
    <h3 class="text-sm font-semibold" :style="{ color: 'var(--text-primary)' }">
      Linha de aprovação
    </h3>
    <div class="grid grid-cols-2 md:grid-cols-5 gap-2">
      <div
        v-for="step in steps"
        :key="step.id"
        class="rounded-md border p-3 text-xs"
        :style="{ borderColor: 'var(--border)' }"
      >
        <strong>{{ step.label }}</strong>
        <p :style="{ color: step.active ? 'var(--status-success)' : 'var(--text-tertiary)' }">
          {{ step.active ? "ok" : "pendente" }}
        </p>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
const props = defineProps<{
  hasDraft: boolean
  hasPreview: boolean
  hasPrompt: boolean
  approved: boolean
}>()

const steps = computed(() => [
  { id: "draft", label: "Draft", active: props.hasDraft },
  { id: "preview", label: "Preview", active: props.hasPreview },
  { id: "prompt", label: "prompt.md", active: props.hasPrompt },
  { id: "approval", label: "Aprovação", active: props.approved },
  { id: "revert", label: "Reversão", active: false },
])
</script>
