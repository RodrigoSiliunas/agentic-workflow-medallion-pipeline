<template>
  <div
    class="flex h-screen overflow-hidden"
    :style="{
      background: 'var(--bg)',
      color: 'var(--text-primary)',
    }"
  >
    <!-- Sidebar global é ocultada quando o Pipeline Editor está em full-bleed -->
    <SidebarNav v-if="!fullBleed" />
    <main class="flex-1 flex flex-col overflow-hidden">
      <slot />
    </main>
  </div>
</template>

<script setup lang="ts">
// Template estilo claude.ai: sidebar persistente + main slot.
// `editorFullBleed` é ativado pela aba Editor do Pipeline Editor V2 para
// ocupar toda a largura do viewport (paridade com o protótipo).
const fullBleed = useState("editorFullBleed", () => false)
</script>
