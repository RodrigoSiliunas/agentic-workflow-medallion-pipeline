<template>
  <div
    class="flex h-screen overflow-hidden"
    :style="{
      background: 'var(--bg)',
      color: 'var(--text-primary)',
    }"
  >
    <SidebarNav />
    <main class="flex-1 flex flex-col overflow-hidden">
      <slot />
    </main>
  </div>
</template>

<script setup lang="ts">
// Template estilo claude.ai: sidebar persistente + main slot.
</script>
