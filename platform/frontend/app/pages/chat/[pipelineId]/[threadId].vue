<template>
  <div class="flex-1 flex flex-col">
    <!-- Header -->
    <header class="p-4 border-b flex items-center gap-3" style="border-color: var(--border-default)">
      <h2 class="font-semibold">{{ route.params.pipelineId }}</h2>
      <span class="text-xs px-2 py-1 rounded-full" style="background: var(--bg-elevated); color: var(--text-tertiary)">
        {{ route.params.threadId }}
      </span>
    </header>

    <!-- Messages (placeholder) -->
    <div class="flex-1 overflow-y-auto p-4">
      <p class="text-center" style="color: var(--text-tertiary)">
        Chat será implementado na Phase 3 do frontend
      </p>
    </div>

    <!-- Input (placeholder) -->
    <div class="p-4 border-t" style="border-color: var(--border-default)">
      <UInput placeholder="Envie uma mensagem..." class="w-full" disabled />
    </div>
  </div>
</template>

<script setup lang="ts">
definePageMeta({ layout: "default" })
const route = useRoute()
</script>
