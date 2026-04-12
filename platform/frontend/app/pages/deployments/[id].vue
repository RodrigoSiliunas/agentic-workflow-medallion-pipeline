<template>
  <div v-if="deployment" class="flex-1 flex flex-col overflow-hidden">
    <!-- Delete confirmation modal -->
    <div
      v-if="showDeleteConfirm"
      class="fixed inset-0 z-50 flex items-center justify-center"
      :style="{ background: 'rgba(0,0,0,0.6)' }"
      @click.self="showDeleteConfirm = false"
    >
      <div
        class="max-w-sm w-full p-6 rounded-[var(--radius-lg)] border"
        :style="{ background: 'var(--surface)', borderColor: 'var(--border)' }"
      >
        <h3 class="text-sm font-semibold mb-2" :style="{ color: 'var(--text-primary)' }">
          Excluir deployment?
        </h3>
        <p class="text-xs mb-4" :style="{ color: 'var(--text-secondary)' }">
          Isso vai remover permanentemente "{{ deployment.config.name }}" e
          todos os logs/steps associados. Recursos ja provisionados na AWS e
          Databricks nao serao afetados.
        </p>
        <div class="flex justify-end gap-2">
          <AppButton variant="ghost" size="sm" @click="showDeleteConfirm = false">
            Cancelar
          </AppButton>
          <AppButton color="error" size="sm" icon="i-heroicons-trash" @click="confirmDelete">
            Excluir
          </AppButton>
        </div>
      </div>
    </div>

    <DeployProgress :deployment="deployment">
      <template #actions>
        <AppButton
          variant="ghost"
          size="sm"
          icon="i-heroicons-trash"
          square
          :style="{ color: 'var(--status-error)' }"
          @click="showDeleteConfirm = true"
        />
      </template>
    </DeployProgress>

    <!-- Databricks Info (show when deployment has pipeline info) -->
    <section
      v-if="deployment.status === 'success'"
      class="px-8 py-4 border-t"
      :style="{ borderColor: 'var(--border)' }"
    >
      <h3 class="text-xs font-semibold uppercase tracking-wider mb-3" :style="{ color: 'var(--text-tertiary)' }">
        Informacoes do Databricks
      </h3>
      <dl class="grid grid-cols-2 gap-x-6 gap-y-2 text-xs">
        <div v-for="item in databricksInfo" :key="item.label">
          <dt :style="{ color: 'var(--text-tertiary)' }">{{ item.label }}</dt>
          <dd class="font-mono" :style="{ color: 'var(--text-primary)' }">{{ item.value }}</dd>
        </div>
      </dl>
    </section>
  </div>
  <EmptyState
    v-else
    icon="face-frown"
    title="Deployment não encontrado"
    description="Esse deployment pode ter sido removido ou nunca existiu."
    class="flex-1"
  >
    <AppButton to="/deployments" icon="i-heroicons-arrow-left">Ver todos deployments</AppButton>
  </EmptyState>
</template>

<script setup lang="ts">
definePageMeta({ layout: "default" })

const route = useRoute()
const store = useDeploymentsStore()

const id = computed(() => String(route.params.id))
const deployment = computed(() => store.getById(id.value))

const showDeleteConfirm = ref(false)

const databricksInfo = computed(() => {
  const d = deployment.value
  if (!d) return []
  const cfg = d.config || {}
  return [
    { label: "Template", value: d.templateSlug },
    { label: "Environment", value: cfg.environment || d.config?.environment || "?" },
    { label: "Deployment ID", value: d.id },
    { label: "Pipeline ID", value: d.pipelineId || "—" },
    { label: "Duracao", value: d.durationMs ? `${Math.round(d.durationMs / 1000)}s` : "—" },
    { label: "Criado em", value: d.createdAt ? new Date(d.createdAt).toLocaleString("pt-BR") : "—" },
  ].filter(i => i.value && i.value !== "—")
})

async function confirmDelete() {
  showDeleteConfirm.value = false
  await store.deleteDeployment(id.value)
  navigateTo("/deployments")
}

// Se nao temos NADA em store, tenta carregar a lista primeiro
if (!deployment.value) {
  await store.load()
}

// Sempre chama refreshOne pra hidratar steps + logs do DB — o endpoint da
// LISTA (`GET /deployments`) retorna `DeploymentListItem` (summary sem logs
// aninhados), entao o registro na store vindo do `load()` tem `logs: []`
// e `steps: []`. So `GET /deployments/{id}` traz o state completo.
await store.refreshOne(id.value)

// Se o deployment esta rodando, subscreve ao SSE pra receber updates ao vivo
onMounted(() => {
  const current = deployment.value
  if (current && (current.status === "pending" || current.status === "running")) {
    store.runSaga(current.id)
  }
})
</script>
