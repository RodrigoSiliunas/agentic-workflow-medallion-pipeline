<template>
  <div class="flex-1 flex items-center justify-center" style="color: var(--text-secondary)">
    <div class="text-center">
      <UIcon name="i-heroicons-chat-bubble-left-right" class="text-4xl mb-4" style="color: var(--brand-primary)" />
      <h2 class="text-xl font-semibold mb-2" style="color: var(--text-primary)">Selecione um pipeline</h2>
      <p class="text-sm">Escolha um pipeline na sidebar para iniciar uma conversa</p>
    </div>
  </div>
</template>

<script setup lang="ts">
definePageMeta({ layout: "default" })
</script>
