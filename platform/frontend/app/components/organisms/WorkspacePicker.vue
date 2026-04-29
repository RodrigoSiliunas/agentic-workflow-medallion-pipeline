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

      <div v-else-if="oauthConfigured === false" class="space-y-3">
        <div
          class="rounded-[var(--radius-md)] border px-3 py-2 text-xs"
          :style="{
            borderColor: 'var(--border)',
            background: 'rgba(99,102,241,0.08)',
            color: 'var(--text-secondary)',
          }"
        >
          OAuth M2M Account-level nao configurado em
          <NuxtLink to="/settings" class="underline" :style="{ color: 'var(--brand-400)' }">
            /settings
          </NuxtLink>
          — sem listagem automatica de workspaces.
          {{ hostFromSettings ? "URL vem do /settings, so falta o Workspace ID." : "Preencha workspace_id + host manualmente." }}
        </div>
        <AppInput
          v-model="manualWorkspaceId"
          label="Workspace ID *"
          placeholder="7474660770649881"
          helper="Numero inteiro que sufixa nomes de recursos no Account Console (ex: compute-credential-{ID}, storage-config-{ID}). Tambem aparece como ?o={ID} na URL ao abrir o workspace."
          @update:model-value="emitState"
        />
        <!-- Host preenchido via /settings — toggle pra override pontual neste deploy -->
        <div v-if="hostFromSettings" class="space-y-1.5">
          <div class="flex items-center justify-between">
            <label class="block text-xs font-medium" :style="{ color: 'var(--text-secondary)' }">
              Workspace Host (FQDN)
            </label>
            <button
              type="button"
              class="text-[10px] underline"
              :style="{ color: 'var(--brand-400)' }"
              @click="overrideHost = !overrideHost"
            >
              {{ overrideHost ? "Cancelar override" : "Sobrescrever neste deploy" }}
            </button>
          </div>
          <div
            v-if="!overrideHost"
            class="px-3 py-2 rounded-[var(--radius-md)] border text-xs flex items-center gap-2"
            :style="{
              borderColor: 'var(--border)',
              background: 'var(--surface)',
              color: 'var(--text-tertiary)',
            }"
          >
            <span>{{ "{databricks_host de /settings}" }}</span>
            <span class="ml-auto text-[10px] px-1.5 py-0.5 rounded-full" :style="{ background: 'rgba(34,197,94,0.15)', color: 'rgb(34,197,94)' }">
              configurado
            </span>
          </div>
          <AppInput
            v-else
            v-model="manualWorkspaceHost"
            placeholder="https://dbc-xxxxxxxx-xxxx.cloud.databricks.com"
            helper="Override apenas neste deploy. /settings continua intacto."
            @update:model-value="emitState"
          />
        </div>
        <AppInput
          v-else
          v-model="manualWorkspaceHost"
          label="Workspace Host (FQDN) *"
          placeholder="https://dbc-xxxxxxxx-xxxx.cloud.databricks.com"
          helper="URL completa do workspace (com https://)"
          @update:model-value="emitState"
        />
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
  /** Host manual digitado (modo existing sem OAuth pra autofill). */
  workspaceHost?: string
  /** Config completa do workspace selecionado — usado pra autofill advanced */
  config?: DatabricksWorkspaceConfig
}

const props = defineProps<{
  /** True quando databricks_host ja esta configurado em /settings.
   * Esconde input manual de host + sinaliza pro backend usar credential da empresa. */
  hostFromSettings?: boolean
}>()

const emit = defineEmits<{
  "update:state": [state: WorkspacePickerState]
}>()

const mode = ref<"existing" | "new">("new")
const selectedWorkspaceId = ref<string>("")
const selectedConfig = ref<DatabricksWorkspaceConfig | null>(null)
const newWorkspaceName = ref<string>("")
const loadingConfig = ref(false)
// Inputs manuais usados quando OAuth M2M nao esta configurado
const manualWorkspaceId = ref<string>("")
const manualWorkspaceHost = ref<string>("")
// User pode forcar override do host vindo de /settings
const overrideHost = ref<boolean>(false)

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

// Quando user toggle override (hostFromSettings = sim), reemit state pra
// backend trocar entre "usar credential da empresa" vs "usar manual host"
watch(overrideHost, () => emitState())

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
  // Em modo "existing":
  //  - Com OAuth M2M configurado: pega workspace_id do dropdown (selectedWorkspaceId)
  //  - Sem OAuth: usa input manual (manualWorkspaceId + manualWorkspaceHost)
  const resolvedWorkspaceId =
    mode.value === "existing"
      ? (oauthConfigured.value === false
          ? manualWorkspaceId.value
          : selectedWorkspaceId.value) || undefined
      : undefined
  // Host override:
  //  - hostFromSettings=true + overrideHost=false: NAO emite host, backend usa credential empresa
  //  - hostFromSettings=true + overrideHost=true: emite manualWorkspaceHost
  //  - hostFromSettings=false: sempre emite manualWorkspaceHost (input visivel)
  const shouldUseSettingsHost =
    mode.value === "existing" &&
    oauthConfigured.value === false &&
    props.hostFromSettings &&
    !overrideHost.value
  const resolvedWorkspaceHost = shouldUseSettingsHost
    ? undefined
    : mode.value === "existing" && oauthConfigured.value === false
      ? manualWorkspaceHost.value || undefined
      : undefined
  emit("update:state", {
    mode: mode.value,
    workspaceId: resolvedWorkspaceId,
    workspaceName: mode.value === "new" ? newWorkspaceName.value || undefined : undefined,
    workspaceHost: resolvedWorkspaceHost,
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
