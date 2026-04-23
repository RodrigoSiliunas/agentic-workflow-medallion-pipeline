<template>
  <div class="space-y-4">
    <div>
      <label
        class="block text-xs font-medium mb-1.5"
        :style="{ color: 'var(--text-secondary)' }"
      >
        Workspace Databricks
      </label>
      <div class="grid grid-cols-2 gap-2">
        <button
          type="button"
          class="px-3 py-2 rounded-[var(--radius-md)] border text-xs font-medium transition-colors"
          :style="modeStyle('existing')"
          @click="selectMode('existing')"
        >
          Usar workspace existente
        </button>
        <button
          type="button"
          class="px-3 py-2 rounded-[var(--radius-md)] border text-xs font-medium transition-colors"
          :style="modeStyle('new')"
          @click="selectMode('new')"
        >
          Criar workspace novo
        </button>
      </div>
    </div>

    <!-- Modo existing -->
    <div v-if="mode === 'existing'" class="space-y-3">
      <div v-if="loading" class="text-xs" :style="{ color: 'var(--text-tertiary)' }">
        Carregando workspaces da Databricks Account...
      </div>

      <div
        v-else-if="oauthConfigured === false"
        class="rounded-[var(--radius-md)] border px-3 py-2 text-xs"
        :style="{
          borderColor: 'var(--border)',
          background: 'var(--surface)',
          color: 'var(--text-secondary)',
        }"
      >
        Databricks Account OAuth nao configurado em
        <NuxtLink to="/settings" class="underline" :style="{ color: 'var(--brand-400)' }">
          /settings
        </NuxtLink>
        — preencha account_id + oauth client_id + secret pra listar workspaces existentes.
      </div>

      <div v-else-if="error" class="text-xs" :style="{ color: 'var(--status-error)' }">
        Falha ao carregar: {{ error }}
      </div>

      <div
        v-else-if="!workspaces.length"
        class="text-xs"
        :style="{ color: 'var(--text-tertiary)' }"
      >
        Nenhum workspace encontrado na Account. Selecione "Criar workspace novo".
      </div>

      <div v-else class="space-y-2">
        <label
          class="block text-xs font-medium"
          :style="{ color: 'var(--text-secondary)' }"
        >
          Workspace
        </label>
        <select
          v-model="selectedWorkspaceId"
          class="w-full px-3 py-2 rounded-[var(--radius-md)] border text-xs"
          :style="{
            background: 'var(--surface)',
            borderColor: 'var(--border)',
            color: 'var(--text-primary)',
          }"
          @change="onSelectWorkspace"
        >
          <option value="">— selecione —</option>
          <option
            v-for="w in workspaces"
            :key="w.workspace_id"
            :value="String(w.workspace_id)"
          >
            {{ w.workspace_name }} ({{ w.workspace_status }} — {{ w.aws_region }})
          </option>
        </select>

        <div v-if="loadingConfig" class="text-xs" :style="{ color: 'var(--text-tertiary)' }">
          Carregando configuracao do workspace...
        </div>
        <div
          v-else-if="selectedConfig"
          class="rounded-[var(--radius-md)] border px-3 py-2 space-y-1 text-xs"
          :style="{ borderColor: 'var(--border)', background: 'var(--surface)' }"
        >
          <div class="flex items-center gap-2">
            <span :style="{ color: checkColor(selectedConfig.network_id) }">
              {{ selectedConfig.network_id ? "✓" : "✗" }}
            </span>
            <span :style="{ color: 'var(--text-secondary)' }">
              Network configurada
            </span>
          </div>
          <div class="flex items-center gap-2">
            <span :style="{ color: checkColor(selectedConfig.root_bucket_name) }">
              {{ selectedConfig.root_bucket_name ? "✓" : "✗" }}
            </span>
            <span :style="{ color: 'var(--text-secondary)' }">
              Root bucket: {{ selectedConfig.root_bucket_name || "ausente" }}
            </span>
          </div>
          <div class="flex items-center gap-2">
            <span :style="{ color: checkColor(selectedConfig.metastore_attached) }">
              {{ selectedConfig.metastore_attached ? "✓" : "✗" }}
            </span>
            <span :style="{ color: 'var(--text-secondary)' }">
              Metastore attached
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Modo new -->
    <div v-else class="space-y-3">
      <AppInput
        v-model="newWorkspaceName"
        label="Nome do workspace"
        placeholder="meu-workspace-prod"
        helper="Nome unico — Databricks vai gerar FQDN tipo dbc-XXXX.cloud.databricks.com"
        @update:model-value="emitState"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { DatabricksWorkspaceConfig } from "~/composables/useDatabricksWorkspaces"
import { useDatabricksWorkspaces } from "~/composables/useDatabricksWorkspaces"

interface WorkspacePickerState {
  mode: "existing" | "new"
  workspaceId?: string
  workspaceName?: string
  /** Config completa do workspace selecionado — usado pra autofill advanced */
  config?: DatabricksWorkspaceConfig
}

const emit = defineEmits<{
  "update:state": [state: WorkspacePickerState]
}>()

const mode = ref<"existing" | "new">("new")
const selectedWorkspaceId = ref<string>("")
const selectedConfig = ref<DatabricksWorkspaceConfig | null>(null)
const newWorkspaceName = ref<string>("")
const loadingConfig = ref(false)

const {
  workspaces,
  oauthConfigured,
  loading,
  error,
  loadWorkspaces,
  fetchWorkspaceConfig,
} = useDatabricksWorkspaces()

onMounted(() => {
  loadWorkspaces()
  emitState()
})

function selectMode(value: "existing" | "new") {
  mode.value = value
  if (value === "existing" && workspaces.value.length === 0 && oauthConfigured.value === null) {
    loadWorkspaces()
  }
  emitState()
}

async function onSelectWorkspace() {
  if (!selectedWorkspaceId.value) {
    selectedConfig.value = null
    emitState()
    return
  }
  loadingConfig.value = true
  try {
    selectedConfig.value = await fetchWorkspaceConfig(Number(selectedWorkspaceId.value))
  } catch (e) {
    selectedConfig.value = null
    console.error("workspace config fetch failed", e)
  } finally {
    loadingConfig.value = false
    emitState()
  }
}

function emitState() {
  emit("update:state", {
    mode: mode.value,
    workspaceId: mode.value === "existing" ? selectedWorkspaceId.value : undefined,
    workspaceName: mode.value === "new" ? newWorkspaceName.value || undefined : undefined,
    config: selectedConfig.value || undefined,
  })
}

function modeStyle(value: "existing" | "new"): Record<string, string> {
  const isActive = mode.value === value
  return {
    background: isActive ? "var(--brand-600)" : "var(--surface)",
    color: isActive ? "white" : "var(--text-secondary)",
    borderColor: isActive ? "var(--brand-600)" : "var(--border)",
  }
}

function checkColor(value: unknown): string {
  return value ? "var(--brand-400)" : "var(--status-error)"
}

defineExpose({
  // Permite o pai resetar/forcar update
  emitState,
})
</script>
