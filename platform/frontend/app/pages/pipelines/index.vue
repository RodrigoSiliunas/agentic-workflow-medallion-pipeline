<template>
  <div class="flex-1 flex flex-col overflow-hidden">
    <header
      class="px-6 pt-6 pb-4 border-b"
      :style="{ borderColor: 'var(--border)' }"
    >
      <h1
        class="text-2xl font-semibold tracking-tight mb-1"
        :style="{ color: 'var(--text-primary)' }"
      >
        Pipelines
      </h1>
      <p class="text-sm" :style="{ color: 'var(--text-secondary)' }">
        Gerencie e monitore seus pipelines de dados.
      </p>
    </header>

    <div class="flex-1 overflow-y-auto px-6 py-6">
      <EmptyState
        v-if="pipelines.length === 0"
        icon="circle-stack"
        title="Nenhum pipeline disponível"
        description="Faça o deploy de um template no marketplace para criar seu primeiro pipeline."
      >
        <AppButton to="/marketplace" icon="i-heroicons-squares-2x2">
          Ver marketplace
        </AppButton>
      </EmptyState>

      <div
        v-else
        class="grid gap-4 grid-cols-1 md:grid-cols-2 xl:grid-cols-3"
      >
        <PipelineCard
          v-for="pipeline in pipelines"
          :key="pipeline.id"
          :pipeline="pipeline"
          @select="(id) => navigateTo('/pipelines/' + id)"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
definePageMeta({ layout: "default" })

const store = usePipelinesStore()
await store.load()

const pipelines = computed(() => store.pipelines)
</script>
