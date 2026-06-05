<template>
  <div class="flex flex-col gap-[10px]">
    <!-- Barra de status de inicialização -->
    <div
      class="flex items-center gap-[10px] rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)] px-[12px] py-[10px]"
    >
      <AppStatusDot tone="warning" :pulse="true" :size="6" />
      <span class="flex-1 text-[13px]" :style="{ color: 'var(--fg-primary)' }">
        Spinning up preview namespace…
      </span>
      <span class="font-mono text-[11px]" :style="{ color: 'var(--fg-tertiary)' }">até 60s</span>
    </div>

    <!-- Grade de 3 colunas com shimmer -->
    <div class="grid gap-[10px]" style="grid-template-columns: repeat(3, 1fr)">
      <div class="shimmer-block" style="height: 130px" />
      <div class="shimmer-block" style="height: 130px" />
      <div class="shimmer-block" style="height: 130px" />
    </div>

    <!-- Bloco alto único -->
    <div class="shimmer-block" style="height: 200px" />
  </div>
</template>

<script setup lang="ts">
// Sem props ou emits — componente puramente visual de loading
</script>

<style scoped>
.shimmer-block {
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
  background: linear-gradient(
    90deg,
    var(--surface) 0%,
    var(--surface-elevated) 50%,
    var(--surface) 100%
  );
  background-size: 200% 100%;
  animation: shimmer 1.6s ease-in-out infinite;
}

@keyframes shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}
</style>
