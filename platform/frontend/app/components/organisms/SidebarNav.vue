<template>
  <aside
    class="w-[320px] flex-shrink-0 flex flex-col h-full border-r"
    :style="{
      background: 'var(--surface)',
      borderColor: 'var(--border)',
    }"
  >
    <!-- Workspace header — clicar leva pra /chat -->
    <NuxtLink
      to="/chat"
      class="px-4 py-4 flex items-center gap-2.5 border-b transition-colors hover:bg-[var(--surface-elevated)]"
      :style="{ borderColor: 'var(--border)' }"
    >
      <SafaLogo variant="icon" :size="28" />
      <div class="flex-1 min-w-0">
        <h1 class="text-sm font-semibold truncate" :style="{ color: 'var(--text-primary)' }">
          Flowertex
        </h1>
        <p class="text-[10px] truncate" :style="{ color: 'var(--text-tertiary)' }">
          Pipeline agent platform
        </p>
      </div>
    </NuxtLink>

    <!-- Module switcher -->
    <div class="px-3 pt-3">
      <ModuleSwitcher />
    </div>

    <!-- Context-aware body -->
    <div class="flex-1 flex flex-col overflow-hidden">
      <!-- CHAT MODE -->
      <template v-if="mode === 'chat'">
        <div class="px-3 pt-3 pb-2 space-y-2">
          <NewThreadButton @click="onNewThread" />
          <AppInput
            v-model="search"
            placeholder="Buscar conversas..."
            icon="i-heroicons-magnifying-glass"
            size="sm"
          />
        </div>

        <div class="px-3 pb-2">
          <button
            v-for="p in pipelinesStore.pipelines"
            :key="p.id"
            class="w-full rounded-[var(--radius-md)] border px-3 py-2 mb-1 transition-colors text-left"
            :class="pipelinesStore.activePipelineId === p.id
              ? 'border-[var(--brand-500)]/40 bg-[var(--surface-elevated)]/80'
              : 'border-[var(--border)] bg-[var(--surface-elevated)]/30 hover:bg-[var(--surface-elevated)]/60'"
            @click="switchPipeline(p.id)"
          >
            <div class="flex items-center justify-between gap-2">
              <div class="flex items-center gap-2 min-w-0">
                <AppIcon name="cpu-chip" size="xs" class="text-[var(--brand-500)] flex-shrink-0" />
                <span
                  class="text-[11px] font-medium truncate"
                  :style="{ color: 'var(--text-secondary)' }"
                >
                  {{ p.name }}
                </span>
              </div>
              <StatusBadge :status="p.status" />
            </div>
          </button>
        </div>

        <ThreadList
          :groups="filteredGroups"
          :active-id="threadsStore.activeThreadId"
          @select="onSelectThread"
          @delete="onDeleteThread"
        />
      </template>

      <!-- MARKETPLACE MODE -->
      <template v-else-if="mode === 'marketplace'">
        <div class="px-3 pt-3 pb-2 space-y-2">
          <AppInput
            v-model="localMarketplaceSearch"
            placeholder="Buscar templates..."
            icon="i-heroicons-magnifying-glass"
            size="sm"
            @update:model-value="onMarketplaceSearch"
          />
        </div>
        <div class="px-3 pb-2 space-y-0.5 flex-1 overflow-y-auto">
          <h4
            class="px-2 pb-1 text-[10px] uppercase tracking-wider font-medium"
            :style="{ color: 'var(--text-tertiary)' }"
          >
            Categorias
          </h4>
          <button
            class="w-full flex items-center gap-2 px-3 py-1.5 rounded-[var(--radius-md)] text-xs text-left transition-colors"
            :style="categoryStyle(null)"
            @click="setCategory(null)"
          >
            <AppIcon name="squares-2x2" size="xs" />
            <span class="flex-1">Todos</span>
            <span class="text-[10px] tabular-nums" :style="{ color: 'var(--text-tertiary)' }">
              {{ templatesStore.templates.length }}
            </span>
          </button>
          <button
            v-for="cat in templatesStore.categories"
            :key="cat"
            class="w-full flex items-center gap-2 px-3 py-1.5 rounded-[var(--radius-md)] text-xs text-left transition-colors"
            :style="categoryStyle(cat)"
            @click="setCategory(cat)"
          >
            <AppIcon :name="categoryIcon(cat)" size="xs" />
            <span class="flex-1">{{ cat }}</span>
            <span class="text-[10px] tabular-nums" :style="{ color: 'var(--text-tertiary)' }">
              {{ countByCategory(cat) }}
            </span>
          </button>

          <h4
            class="px-2 pt-4 pb-1 text-[10px] uppercase tracking-wider font-medium"
            :style="{ color: 'var(--text-tertiary)' }"
          >
            Atalhos
          </h4>
          <NuxtLink
            to="/deployments"
            class="w-full flex items-center gap-2 px-3 py-1.5 rounded-[var(--radius-md)] text-xs transition-colors text-[var(--text-secondary)] hover:bg-[var(--surface-elevated)]"
          >
            <AppIcon name="rocket-launch" size="xs" class="text-[var(--brand-500)]" />
            <span>Deployments ativos</span>
          </NuxtLink>
        </div>
      </template>

      <!-- CHANNELS MODE -->
      <template v-else-if="mode === 'channels'">
        <div class="px-3 pt-3 pb-2">
          <AppButton
            size="sm"
            icon="i-heroicons-plus"
            class="w-full justify-center"
            @click="onNewChannelClick"
          >
            Nova instância
          </AppButton>
        </div>
        <div class="px-3 pb-2 flex-1 overflow-y-auto space-y-0.5">
          <h4
            class="px-2 pb-1 text-[10px] uppercase tracking-wider font-medium"
            :style="{ color: 'var(--text-tertiary)' }"
          >
            Canais ativos
          </h4>
          <div
            v-for="instance in channelsStore.instances.filter((i) => i.state !== 'disconnected')"
            :key="instance.id"
            class="w-full flex items-center gap-2 px-3 py-2 rounded-[var(--radius-md)] text-xs"
            :style="{ color: 'var(--text-secondary)' }"
          >
            <ChannelIcon :channel="instance.channel" size="xs" />
            <span class="flex-1 truncate">{{ instance.name }}</span>
            <span
              class="w-1.5 h-1.5 rounded-full flex-shrink-0"
              :class="{ 'status-pulse': instance.state === 'connecting' }"
              :style="{ background: channelDotColor(instance.state) }"
            />
          </div>
          <EmptyState
            v-if="channelsStore.instances.length === 0"
            icon="phone"
            title="Sem canais"
            description="Conecte WhatsApp, Discord ou Telegram."
          />
        </div>
      </template>

      <!-- DEPLOYMENTS MODE -->
      <template v-else-if="mode === 'deployments'">
        <div class="px-3 pt-3 pb-2">
          <AppButton to="/marketplace" size="sm" icon="i-heroicons-plus" class="w-full justify-center">
            Novo deploy
          </AppButton>
        </div>
        <div class="px-3 pb-2 flex-1 overflow-y-auto space-y-0.5">
          <h4
            class="px-2 pb-1 text-[10px] uppercase tracking-wider font-medium"
            :style="{ color: 'var(--text-tertiary)' }"
          >
            Recentes
          </h4>
          <div
            v-for="d in deploymentsStore.list.slice(0, 10)"
            :key="d.id"
            class="group w-full flex items-center gap-2 px-3 py-2 rounded-[var(--radius-md)] text-xs transition-colors cursor-pointer"
            :class="isActiveDeployment(d.id) ? 'bg-[var(--surface-elevated)] text-[var(--text-primary)]' : 'text-[var(--text-secondary)] hover:bg-[var(--surface-elevated)]/60'"
            @click="navigateTo(`/deployments/${d.id}`)"
            @dblclick.stop="startRename(d)"
          >
            <span class="w-1.5 h-1.5 rounded-full flex-shrink-0" :class="{ 'status-pulse': d.status === 'running' }" :style="{ background: dotForStatus(d.status) }" />
            <input
              v-if="renamingId === d.id"
              v-model="renameValue"
              class="flex-1 bg-transparent border-b border-[var(--brand-500)] outline-none text-xs"
              :style="{ color: 'var(--text-primary)' }"
              @keydown.enter="confirmRename(d.id)"
              @keydown.escape="renamingId = null"
              @blur="confirmRename(d.id)"
            >
            <span v-else class="flex-1 truncate">{{ d.config.name }}</span>
            <button
              v-if="renamingId !== d.id"
              class="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 rounded hover:bg-[var(--surface-elevated)]"
              :style="{ color: 'var(--status-error)' }"
              @click.stop="handleDeleteDeploy(d.id, d.config.name)"
            >
              <AppIcon name="trash" size="xs" />
            </button>
          </div>

          <EmptyState
            v-if="deploymentsStore.list.length === 0"
            icon="rocket-launch"
            title="Sem deployments"
            description="Comece um deploy no marketplace."
          />
        </div>
      </template>
    </div>

    <!-- User footer -->
    <div
      class="px-3 py-3 border-t flex items-center gap-2"
      :style="{ borderColor: 'var(--border)' }"
    >
      <AppAvatar size="sm" :name="authStore.userName || 'Usuario'" />
      <div class="flex-1 min-w-0">
        <p class="text-[12px] font-medium truncate" :style="{ color: 'var(--text-primary)' }">
          {{ authStore.userName || "Visitante" }}
        </p>
        <p class="text-[10px] truncate capitalize" :style="{ color: 'var(--text-tertiary)' }">
          {{ authStore.userRole }}
        </p>
      </div>
      <AppButton variant="ghost" size="sm" icon="i-heroicons-question-mark-circle" square to="/help" />
      <AppButton variant="ghost" size="sm" icon="i-heroicons-cog-6-tooth" square to="/settings" />
      <AppButton variant="ghost" size="sm" icon="i-heroicons-arrow-right-on-rectangle" square @click="handleLogout" />
    </div>

    <!-- Modal: selecionar pipeline pra nova conversa -->
    <div
      v-if="showPipelinePicker"
      class="fixed inset-0 z-50 flex items-center justify-center"
      :style="{ background: 'rgba(0,0,0,0.6)' }"
      @click.self="showPipelinePicker = false"
    >
      <div
        class="max-w-sm w-full mx-4 p-5 rounded-[var(--radius-lg)] border"
        :style="{ background: 'var(--surface)', borderColor: 'var(--border)' }"
      >
        <h3 class="text-sm font-semibold mb-1" :style="{ color: 'var(--text-primary)' }">
          Selecionar pipeline
        </h3>
        <p class="text-xs mb-4" :style="{ color: 'var(--text-tertiary)' }">
          Cada conversa e vinculada a um pipeline pra dar contexto ao agente.
        </p>
        <div class="space-y-2">
          <button
            v-for="p in pipelinesStore.pipelines"
            :key="p.id"
            class="w-full flex items-center gap-3 px-3 py-2.5 rounded-[var(--radius-md)] border text-left transition-colors hover:border-[var(--brand-500)]/50 hover:bg-[var(--surface-elevated)]"
            :style="{ borderColor: 'var(--border)' }"
            @click="createThreadForPipeline(p.id)"
          >
            <AppIcon name="cpu-chip" size="sm" class="text-[var(--brand-500)] flex-shrink-0" />
            <div class="flex-1 min-w-0">
              <p class="text-xs font-medium truncate" :style="{ color: 'var(--text-primary)' }">
                {{ p.name }}
              </p>
              <p class="text-[10px]" :style="{ color: 'var(--text-tertiary)' }">
                {{ p.status === 'SUCCESS' ? 'Ativo' : 'Parado' }}
              </p>
            </div>
            <AppIcon name="chevron-right" size="xs" :style="{ color: 'var(--text-tertiary)' }" />
          </button>
        </div>
        <button
          class="w-full mt-3 text-xs text-center py-1.5"
          :style="{ color: 'var(--text-tertiary)' }"
          @click="showPipelinePicker = false"
        >
          Cancelar
        </button>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import type { OmniInstanceState } from "~/types/channel"
import type { DeploymentStatus } from "~/types/deployment"

const route = useRoute()
const threadsStore = useThreadsStore()
const pipelinesStore = usePipelinesStore()
const authStore = useAuthStore()
const templatesStore = useTemplatesStore()
const deploymentsStore = useDeploymentsStore()
const channelsStore = useChannelsStore()

// Carrega pipelines da empresa no mount — necessario pra sidebar mostrar
// o pipeline ativo e pro chat funcionar com dados reais.
onMounted(() => {
  if (!pipelinesStore.loaded) {
    pipelinesStore.load()
  }
})

// Carrega canais quando entra no mode channels
watch(
  () => route.path,
  () => {
    if (route.path.startsWith("/channels") && !channelsStore.loaded) {
      channelsStore.load()
    }
  },
  { immediate: true },
)

// Carrega threads do pipeline ativo quando entra no chat
watch(
  () => [route.path, pipelinesStore.activePipelineId] as const,
  async ([path, pid]) => {
    if (path.startsWith("/chat") && pid) {
      await threadsStore.loadForPipeline(pid)
    }
  },
  { immediate: true },
)

const mode = computed<"chat" | "marketplace" | "deployments" | "channels">(() => {
  if (route.path.startsWith("/marketplace") || route.path.startsWith("/deploy/")) return "marketplace"
  if (route.path.startsWith("/deployments")) return "deployments"
  if (route.path.startsWith("/channels")) return "channels"
  return "chat"
})

// --- CHAT ---
const search = ref("")
const activePipeline = computed(() => pipelinesStore.activePipeline)

const filteredGroups = computed(() => {
  const groups = threadsStore.groupedByBucket(activePipeline.value?.id)
  if (!search.value.trim()) return groups
  const q = search.value.toLowerCase()
  const result: Record<string, (typeof groups)[string]> = {}
  for (const [bucket, items] of Object.entries(groups)) {
    const filtered = items.filter((t) => t.title.toLowerCase().includes(q))
    if (filtered.length > 0) result[bucket] = filtered
  }
  return result
})

const showPipelinePicker = ref(false)

async function onNewThread() {
  const pipelines = pipelinesStore.pipelines
  if (pipelines.length === 0) {
    navigateTo("/chat")
    return
  }
  if (pipelines.length === 1) {
    // So 1 pipeline — cria direto sem modal
    await createThreadForPipeline(pipelines[0].id)
    return
  }
  // Multiplos pipelines — mostra modal pra usuario escolher
  showPipelinePicker.value = true
}

function switchPipeline(pipelineId: string) {
  pipelinesStore.setActive(pipelineId)
  threadsStore.loadForPipeline(pipelineId)
  navigateTo("/chat")
}

async function createThreadForPipeline(pipelineId: string) {
  showPipelinePicker.value = false
  pipelinesStore.setActive(pipelineId)
  const thread = await threadsStore.create("Nova conversa", pipelineId)
  await threadsStore.loadForPipeline(pipelineId)
  navigateTo(`/chat/${thread.id}`)
}

function onSelectThread(id: string) {
  threadsStore.setActive(id)
  navigateTo(`/chat/${id}`)
}

function onDeleteThread(id: string) {
  threadsStore.remove(id)
  if (threadsStore.activeThreadId === null) {
    navigateTo("/chat")
  }
}

// --- MARKETPLACE ---
const localMarketplaceSearch = ref(templatesStore.searchQuery)

function onMarketplaceSearch(v: string) {
  templatesStore.setSearch(v)
}

function setCategory(cat: string | null) {
  templatesStore.setCategory(cat)
  if (route.path !== "/marketplace") navigateTo("/marketplace")
}

function categoryStyle(cat: string | null): Record<string, string> {
  const isActive = templatesStore.activeCategory === cat
  return {
    background: isActive ? "var(--surface-elevated)" : "transparent",
    color: isActive ? "var(--text-primary)" : "var(--text-secondary)",
    borderLeft: isActive ? "2px solid var(--brand-500)" : "2px solid transparent",
  }
}

const CATEGORY_ICONS: Record<string, string> = {
  ETL: "cpu-chip",
  CRM: "building-office-2",
  "E-commerce": "shopping-cart",
  Analytics: "chart-bar",
  Observability: "eye",
}

function categoryIcon(cat: string): string {
  return CATEGORY_ICONS[cat] ?? "squares-2x2"
}

function countByCategory(cat: string): number {
  return templatesStore.templates.filter((t) => t.category === cat).length
}

// --- DEPLOYMENTS ---
const renamingId = ref<string | null>(null)
const renameValue = ref("")

function startRename(d: { id: string; config: { name: string } }) {
  renamingId.value = d.id
  renameValue.value = d.config.name
  nextTick(() => {
    const input = document.querySelector('input[class*="bg-transparent"]') as HTMLInputElement
    input?.focus()
    input?.select()
  })
}

async function confirmRename(id: string) {
  if (!renameValue.value.trim() || !renamingId.value) {
    renamingId.value = null
    return
  }
  // Update deployment name via API
  try {
    const api = useApiClient()
    await api.put(`/deployments/${id}`, { name: renameValue.value.trim() })
    await deploymentsStore.load(true)
  } catch {
    // silently fail
  }
  renamingId.value = null
}

async function handleDeleteDeploy(id: string, name: string) {
  if (!confirm(`Excluir deployment "${name}"?`)) return
  await deploymentsStore.deleteDeployment(id)
}

function isActiveDeployment(id: string): boolean {
  return route.path === `/deployments/${id}`
}

function dotForStatus(status: DeploymentStatus): string {
  switch (status) {
    case "success":
      return "var(--status-success)"
    case "failed":
      return "var(--status-error)"
    case "running":
      return "var(--status-warning)"
    case "cancelled":
      return "var(--text-tertiary)"
    default:
      return "var(--text-tertiary)"
  }
}

// --- CHANNELS ---
function channelDotColor(state: OmniInstanceState): string {
  switch (state) {
    case "connected":
      return "var(--status-success)"
    case "connecting":
      return "var(--status-warning)"
    case "failed":
      return "var(--status-error)"
    default:
      return "var(--text-tertiary)"
  }
}

function onNewChannelClick() {
  navigateTo({ path: "/channels", query: { new: "1" } })
}

async function handleLogout() {
  await authStore.logout()
  navigateTo("/")
}
</script>
