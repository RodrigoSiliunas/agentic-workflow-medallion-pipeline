<template>
  <div class="flex items-center gap-2">
    <!-- Ícone/indicador de estado -->
    <AppStatusDot
      v-if="check.state === 'running'"
      tone="warning"
      :pulse="true"
      :size="8"
    />
    <AppIcon
      v-else-if="check.state === 'ok'"
      name="check-circle"
      size="sm"
      :style="{ color: 'var(--status-success)' }"
    />
    <AppIcon
      v-else-if="check.state === 'fail'"
      name="x-circle"
      size="sm"
      :style="{ color: 'var(--status-error)' }"
    />
    <!-- pending: relógio -->
    <AppIcon v-else name="clock" size="sm" :style="{ color: 'var(--fg-tertiary)' }" />

    <!-- Rótulo do check -->
    <span
      class="text-[12px]"
      :style="{ color: check.state === 'fail' ? 'var(--status-error)' : 'var(--fg-secondary)' }"
    >
      {{ check.label }}
    </span>
  </div>
</template>

<script setup lang="ts">
import type { ValidationCheck } from "~/types/pipeline-editor-v2"

defineProps<{
  check: ValidationCheck
}>()
</script>
