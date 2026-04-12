<template>
  <DeploymentsList />
</template>

<script setup lang="ts">
definePageMeta({ layout: "default" })

const store = useDeploymentsStore()
await store.load()
</script>
