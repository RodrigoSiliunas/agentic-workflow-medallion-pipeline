<template>
  <LandingCardShell
    eyebrow="Observer Agent"
    title="Run quebra. Claude conserta."
    description="Falhou? O agente analisa logs, código e schema, propõe fix e abre PR no GitHub."
  >
    <div class="px-6 pb-6 space-y-2.5">
      <!-- Timeline item: FAIL -->
      <div
        class="flex items-start gap-3 rounded-[var(--radius-md)] border p-3"
        :style="{
          borderColor: 'rgba(239, 68, 68, 0.3)',
          background: 'rgba(239, 68, 68, 0.05)',
        }"
      >
        <div
          class="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0"
          :style="{ background: 'var(--status-error)' }"
        >
          <svg viewBox="0 0 20 20" fill="white" class="w-3.5 h-3.5">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z" clip-rule="evenodd" />
          </svg>
        </div>
        <div class="min-w-0 flex-1">
          <p class="text-[11px] font-medium" :style="{ color: 'var(--text-primary)' }">
            bronze_ingestion falhou
          </p>
          <p class="text-[10px] font-[var(--font-mono)] truncate" :style="{ color: 'var(--status-error)' }">
            OutOfMemoryError: GC limit
          </p>
        </div>
        <span class="text-[10px] tabular-nums" :style="{ color: 'var(--text-tertiary)' }">14:32</span>
      </div>

      <!-- Connector -->
      <div class="flex justify-center">
        <div class="w-px h-3" :style="{ background: 'var(--border)' }" />
      </div>

      <!-- Timeline item: DIAGNOSE -->
      <div
        class="flex items-start gap-3 rounded-[var(--radius-md)] border p-3"
        :style="{
          borderColor: 'rgba(127, 34, 254, 0.3)',
          background: 'rgba(127, 34, 254, 0.05)',
        }"
      >
        <div
          class="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0"
          :style="{ background: 'var(--brand-600)' }"
        >
          <svg viewBox="0 0 20 20" fill="white" class="w-3.5 h-3.5">
            <path d="M9 4.804A7.968 7.968 0 005.5 4c-1.255 0-2.443.29-3.5.804v10A7.969 7.969 0 015.5 14c1.669 0 3.218.51 4.5 1.385A7.962 7.962 0 0114.5 14c1.255 0 2.443.29 3.5.804v-10A7.968 7.968 0 0014.5 4c-1.255 0-2.443.29-3.5.804V12a1 1 0 11-2 0V4.804z" />
          </svg>
        </div>
        <div class="min-w-0 flex-1">
          <p class="text-[11px] font-medium" :style="{ color: 'var(--text-primary)' }">
            Claude Opus analisou
          </p>
          <p class="text-[10px]" :style="{ color: 'var(--text-secondary)' }">
            Causa raiz: pandas+boto3 no driver.
            <span class="font-[var(--font-mono)]" :style="{ color: 'var(--brand-400)' }">confiança: 94%</span>
          </p>
        </div>
        <span class="text-[10px] tabular-nums" :style="{ color: 'var(--text-tertiary)' }">14:33</span>
      </div>

      <!-- Connector -->
      <div class="flex justify-center">
        <div class="w-px h-3" :style="{ background: 'var(--border)' }" />
      </div>

      <!-- Timeline item: PR CREATED -->
      <div
        class="flex items-start gap-3 rounded-[var(--radius-md)] border p-3"
        :style="{
          borderColor: 'rgba(16, 185, 129, 0.3)',
          background: 'rgba(16, 185, 129, 0.05)',
        }"
      >
        <div
          class="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0"
          :style="{ background: 'var(--status-success)' }"
        >
          <svg viewBox="0 0 20 20" fill="white" class="w-3.5 h-3.5">
            <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
          </svg>
        </div>
        <div class="min-w-0 flex-1">
          <p class="text-[11px] font-medium" :style="{ color: 'var(--text-primary)' }">
            PR #15 aberto
          </p>
          <p class="text-[10px] font-[var(--font-mono)] truncate" :style="{ color: 'var(--text-secondary)' }">
            fix/agent-auto-bronze-oom
          </p>
        </div>
        <span class="text-[10px] tabular-nums" :style="{ color: 'var(--text-tertiary)' }">14:34</span>
      </div>

      <!-- Footer stats -->
      <div
        class="flex items-center justify-between pt-3 mt-3 border-t text-[10px]"
        :style="{ borderColor: 'var(--border)', color: 'var(--text-tertiary)' }"
      >
        <span>Custo total: <span class="tabular-nums font-medium" :style="{ color: 'var(--text-secondary)' }">$0.21</span></span>
        <span>Tempo: <span class="tabular-nums font-medium" :style="{ color: 'var(--text-secondary)' }">2min</span></span>
      </div>
    </div>
  </LandingCardShell>
</template>

<script setup lang="ts">
// puro visual, sem state
</script>
