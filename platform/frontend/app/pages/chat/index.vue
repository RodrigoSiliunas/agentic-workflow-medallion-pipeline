<template>
  <div class="flex-1 flex flex-col overflow-hidden relative">
    <div class="hero-blur-purple top-[-150px] left-[50%] -translate-x-1/2" />

    <div class="flex-1 overflow-y-auto">
      <div class="max-w-3xl mx-auto px-6 py-16 relative">
        <div class="text-center mb-12">
          <div
            class="w-12 h-12 mx-auto mb-5 rounded-[var(--radius-lg)] flex items-center justify-center"
            :style="{ background: 'var(--brand-600)' }"
          >
            <AppIcon name="sparkles" size="md" class="text-white" />
          </div>
          <h1
            class="text-3xl font-semibold mb-2 tracking-tight"
            :style="{ color: 'var(--text-primary)' }"
          >
            Converse com o agente
          </h1>
          <p class="text-sm max-w-md mx-auto" :style="{ color: 'var(--text-secondary)' }">
            Investigue runs, descubra falhas, revise custos e deixe o Observer Agent
            corrigir bugs do pipeline automaticamente.
          </p>
        </div>

        <ObservabilityWidget />

        <div class="grid grid-cols-1 md:grid-cols-2 gap-3 mb-8">
          <button
            v-for="suggestion in suggestions"
            :key="suggestion.title"
            class="text-left rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-elevated)] hover:border-[var(--brand-500)]/40 transition-colors p-4"
            @click="startWith(suggestion.prompt)"
          >
            <div class="flex items-center gap-2 mb-1.5">
              <AppIcon
                :name="suggestion.icon"
                size="sm"
                class="text-[var(--brand-500)]"
              />
              <h3 class="text-sm font-medium" :style="{ color: 'var(--text-primary)' }">
                {{ suggestion.title }}
              </h3>
            </div>
            <p class="text-[11px]" :style="{ color: 'var(--text-tertiary)' }">
              {{ suggestion.description }}
            </p>
          </button>
        </div>

        <div class="max-w-2xl mx-auto">
          <MessageInput @send="startWith" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
definePageMeta({ layout: "default" })

const threadsStore = useThreadsStore()

const suggestions = [
  {
    icon: "exclamation-triangle",
    title: "Por que o bronze falhou?",
    description: "Investigar último run com status FAILED",
    prompt: "Por que o bronze_ingestion falhou hoje?",
  },
  {
    icon: "currency-dollar",
    title: "Quanto o Observer gastou?",
    description: "Breakdown de custos Claude Opus nos últimos 30 dias",
    prompt: "Qual o custo total do Observer esse mês?",
  },
  {
    icon: "signal",
    title: "Status do pipeline",
    description: "Ver último run, tasks, durações",
    prompt: "Qual o status atual do medallion_pipeline_whatsapp?",
  },
  {
    icon: "code-bracket",
    title: "PRs abertos pelo agente",
    description: "Listar PRs criados automaticamente no GitHub",
    prompt: "Quais PRs o Observer abriu esta semana?",
  },
]

const pipelinesStore = usePipelinesStore()

async function startWith(prompt: string) {
  await pipelinesStore.load()
  const pipelineId = pipelinesStore.activePipeline?.id
  if (!pipelineId) return
  const thread = await threadsStore.create("Nova conversa", pipelineId)
  threadsStore.setActive(thread.id)
  navigateTo({ path: `/chat/${thread.id}`, query: { seed: prompt } })
}
</script>
