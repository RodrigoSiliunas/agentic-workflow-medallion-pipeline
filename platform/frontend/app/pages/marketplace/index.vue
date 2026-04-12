<template>
  <div class="flex-1 flex flex-col overflow-hidden">
    <header
      class="px-6 pt-6 pb-2 border-b"
      :style="{ borderColor: 'var(--border)' }"
    >
      <h1
        class="text-2xl font-semibold tracking-tight mb-1"
        :style="{ color: 'var(--text-primary)' }"
      >
        Marketplace
      </h1>
      <p class="text-sm pb-5" :style="{ color: 'var(--text-secondary)' }">
        Templates de pipeline prontos para deploy one-click na sua conta AWS + Databricks.
      </p>
    </header>
    <MarketplaceGrid />
  </div>
</template>

<script setup lang="ts">
definePageMeta({ layout: "default" })

const templatesStore = useTemplatesStore()
await templatesStore.load()
</script>
