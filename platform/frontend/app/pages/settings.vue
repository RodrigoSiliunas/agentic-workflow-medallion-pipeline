<template>
  <div class="flex-1 p-8 overflow-y-auto">
    <h1 class="text-2xl font-semibold mb-6">Configurações</h1>
    <p style="color: var(--text-secondary)">Implementado na Phase 4 do frontend</p>
  </div>
</template>

<script setup lang="ts">
definePageMeta({ layout: "default", middleware: ["role"], role: "admin" })
</script>
