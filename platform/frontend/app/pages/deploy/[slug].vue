<template>
  <DeployWizard v-if="template" :template="template" />
  <EmptyState
    v-else
    icon="face-frown"
    title="Template não encontrado"
    description="Não foi possível carregar o template para deploy."
    class="flex-1"
  >
    <AppButton to="/marketplace" icon="i-heroicons-arrow-left">Voltar ao marketplace</AppButton>
  </EmptyState>
</template>

<script setup lang="ts">
definePageMeta({ layout: "default" })

const route = useRoute()
const store = useTemplatesStore()
await store.load()
const template = computed(() => store.getBySlug(String(route.params.slug)))
</script>
