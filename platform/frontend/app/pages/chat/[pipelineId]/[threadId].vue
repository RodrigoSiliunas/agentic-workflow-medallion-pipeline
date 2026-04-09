<template>
  <div class="flex-1 flex flex-col">
    <!-- Header -->
    <header
      class="px-4 py-3 border-b flex items-center gap-3"
      style="border-color: var(--border-default); background: var(--bg-surface)"
    >
      <h2 class="font-semibold text-sm">{{ route.params.pipelineId }}</h2>
      <span
        class="text-[10px] px-2 py-0.5 rounded-full font-mono"
        style="background: var(--bg-elevated); color: var(--text-tertiary)"
      >
        {{ String(route.params.threadId).slice(0, 8) }}
      </span>
    </header>

    <!-- Chat -->
    <ChatWindow :thread-id="String(route.params.threadId)" />
  </div>
</template>

<script setup lang="ts">
definePageMeta({ layout: "default" })
const route = useRoute()
</script>
