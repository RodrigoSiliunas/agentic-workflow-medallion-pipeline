<template>
  <AppPill
    v-if="source"
    :tone="meta.tone"
    :icon="meta.icon"
    size="xs"
    dot
    :pulse="true"
  >
    {{ meta.label }}
  </AppPill>
</template>

<script setup lang="ts">
import type { SourceOfTruth } from "~/types/pipeline-editor-v2"

const props = defineProps<{
  source?: SourceOfTruth
}>()

const SOURCE_MAP: Record<
  NonNullable<SourceOfTruth>,
  { icon: string; label: string; tone: "brand" | "info" }
> = {
  chat:    { icon: "chat-bubble-left-right", label: "Fonte: Chat",    tone: "brand" },
  builder: { icon: "squares-plus",           label: "Fonte: Builder", tone: "info" },
}

const meta = computed(() =>
  props.source ? SOURCE_MAP[props.source] : SOURCE_MAP.chat,
)
</script>
