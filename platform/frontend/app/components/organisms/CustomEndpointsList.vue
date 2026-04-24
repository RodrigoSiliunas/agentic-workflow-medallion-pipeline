<template>
  <div class="space-y-3">
    <div
      class="p-3 rounded-[var(--radius-md)] text-xs space-y-1"
      :style="{
        background: 'rgba(99,102,241,0.08)',
        border: '1px solid rgba(99,102,241,0.25)',
        color: 'var(--text-secondary)',
      }"
    >
      <p class="font-medium" :style="{ color: 'var(--text-primary)' }">
        Custom LLM Endpoints (opcional)
      </p>
      <p>
        Use modelos locais (Ollama, vLLM, LM Studio) ou APIs OpenAI-compatible
        (OpenRouter, Together, Anyscale). Funciona com qualquer servidor que
        implemente <code>POST /v1/chat/completions</code>.
      </p>
      <p class="text-[10px]" :style="{ color: 'var(--text-tertiary)' }">
        Recomendado pra RTX 3070 8GB: <code>qwen3.5:9b</code> ou <code>gemma4:e2b</code>
      </p>
    </div>

    <div v-if="loading" class="text-xs" :style="{ color: 'var(--text-tertiary)' }">
      Carregando endpoints...
    </div>

    <div v-else-if="!endpoints.length" class="text-xs" :style="{ color: 'var(--text-tertiary)' }">
      Nenhum endpoint cadastrado. Clique em "Adicionar endpoint" abaixo.
    </div>

    <div
      v-for="ep in endpoints"
      v-else
      :key="ep.id"
      class="p-3 rounded-[var(--radius-md)] border space-y-2"
      :style="{ borderColor: 'var(--border)', background: 'var(--surface)' }"
    >
      <div class="flex items-center justify-between gap-2">
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-2">
            <h4 class="text-sm font-semibold" :style="{ color: 'var(--text-primary)' }">
              {{ ep.name }}
            </h4>
            <span
              class="text-[10px] px-1.5 py-0.5 rounded-full"
              :style="badgeStyle(ep.last_test_status)"
            >
              {{ ep.last_test_status || 'untested' }}
            </span>
            <span
              v-if="!ep.enabled"
              class="text-[10px] px-1.5 py-0.5 rounded-full"
              :style="{ background: 'rgba(239,68,68,0.15)', color: 'var(--status-error)' }"
            >disabled</span>
          </div>
          <p class="text-[11px] truncate" :style="{ color: 'var(--text-tertiary)' }">
            <code>{{ ep.base_url }}</code>
          </p>
          <p class="text-[11px]" :style="{ color: 'var(--text-secondary)' }">
            {{ ep.models.length }} modelo(s)
            <span v-if="ep.has_api_key">· auth</span>
            <span v-else>· sem auth</span>
          </p>
          <p
            v-if="ep.models.length"
            class="text-[10px] truncate"
            :style="{ color: 'var(--text-tertiary)' }"
          >
            {{ ep.models.map((m) => m.id).join(', ') }}
          </p>
        </div>
        <div class="flex gap-1 flex-shrink-0">
          <button
            type="button"
            class="text-[11px] px-2 py-1 rounded-[var(--radius-sm)] border"
            :style="btnStyle"
            @click="refreshModels(ep)"
          >
            Atualizar models
          </button>
          <button
            type="button"
            class="text-[11px] px-2 py-1 rounded-[var(--radius-sm)] border"
            :style="btnStyle"
            @click="startEdit(ep)"
          >
            Editar
          </button>
          <button
            type="button"
            class="text-[11px] px-2 py-1 rounded-[var(--radius-sm)] border"
            :style="dangerStyle"
            @click="confirmDelete(ep)"
          >
            Deletar
          </button>
        </div>
      </div>
    </div>

    <button
      type="button"
      class="w-full px-3 py-2 rounded-[var(--radius-md)] border text-xs font-medium"
      :style="{
        borderColor: 'var(--brand-600)',
        background: 'rgba(99,102,241,0.08)',
        color: 'var(--brand-400)',
      }"
      @click="startCreate"
    >
      + Adicionar endpoint customizado
    </button>

    <!-- Form modal inline -->
    <div
      v-if="formOpen"
      class="p-4 rounded-[var(--radius-lg)] border space-y-3"
      :style="{ borderColor: 'var(--brand-600)', background: 'var(--surface)' }"
    >
      <h4 class="text-sm font-semibold" :style="{ color: 'var(--text-primary)' }">
        {{ editingId ? 'Editar endpoint' : 'Novo endpoint' }}
      </h4>

      <AppInput
        v-model="form.name"
        label="Nome *"
        placeholder="Meu Ollama Local"
      />
      <AppInput
        v-model="form.base_url"
        label="Base URL *"
        placeholder="http://ollama:11434/v1"
        helper="Endpoint OpenAI-compatible. Ex: http://ollama:11434/v1, https://api.openrouter.ai/api/v1"
      />
      <AppInput
        v-model="form.api_key"
        label="API Key (opcional)"
        type="password"
        placeholder="sk-... ou deixe vazio pra Ollama"
        helper="Vazio pra Ollama. OpenRouter/Together exigem chave."
      />

      <div class="flex gap-2">
        <button
          type="button"
          class="px-3 py-1.5 rounded-[var(--radius-sm)] border text-xs font-medium"
          :style="btnStyle"
          :disabled="!form.base_url || testing"
          @click="testConnection"
        >
          {{ testing ? 'Testando...' : 'Testar conexao' }}
        </button>
      </div>

      <div
        v-if="testResult"
        class="rounded-[var(--radius-md)] border px-3 py-2 text-xs"
        :style="testResult.success
          ? { borderColor: 'var(--brand-600)', background: 'rgba(34,197,94,0.08)', color: 'rgb(34,197,94)' }
          : { borderColor: 'var(--status-error)', background: 'rgba(239,68,68,0.08)', color: 'var(--status-error)' }"
      >
        <p class="font-medium">
          {{ testResult.success
            ? `✓ Conexao OK (${testResult.server_type || 'unknown'})`
            : `✗ Falhou: ${testResult.error || 'desconhecido'}` }}
        </p>
        <div v-if="testResult.discovered_models.length" class="mt-2 space-y-1">
          <p class="text-[11px]" :style="{ color: 'var(--text-secondary)' }">
            Modelos descobertos ({{ testResult.discovered_models.length }}):
          </p>
          <label
            v-for="m in testResult.discovered_models"
            :key="m.id"
            class="flex items-center gap-2 text-[11px]"
            :style="{ color: 'var(--text-secondary)' }"
          >
            <input
              v-model="form.models"
              :value="m"
              type="checkbox"
              class="accent-[var(--brand-600)]"
            >
            <code>{{ m.id }}</code>
          </label>
        </div>
      </div>

      <div class="flex gap-2 justify-end">
        <button
          type="button"
          class="px-3 py-1.5 rounded-[var(--radius-sm)] border text-xs"
          :style="btnStyle"
          @click="cancelForm"
        >
          Cancelar
        </button>
        <button
          type="button"
          class="px-3 py-1.5 rounded-[var(--radius-sm)] text-xs font-medium"
          :style="{
            background: 'var(--brand-600)',
            color: 'white',
            opacity: !canSubmit ? '0.5' : '1',
          }"
          :disabled="!canSubmit"
          @click="submit"
        >
          {{ editingId ? 'Salvar' : 'Criar' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  type CustomLLMEndpoint,
  type CustomLLMModelInfo,
  type TestEndpointResult,
  useCustomEndpoints,
} from "~/composables/useCustomEndpoints"

const toast = useToast()
const {
  endpoints,
  loading,
  load,
  create,
  update,
  remove,
  testConnection: testApi,
  refreshModels: refreshApi,
} = useCustomEndpoints()

const formOpen = ref(false)
const editingId = ref<string | null>(null)
const testing = ref(false)
const testResult = ref<TestEndpointResult | null>(null)

const form = reactive<{
  name: string
  base_url: string
  api_key: string
  models: CustomLLMModelInfo[]
}>({
  name: "",
  base_url: "",
  api_key: "",
  models: [],
})

const canSubmit = computed(
  () => form.name.trim().length >= 2 && form.base_url.trim().length >= 8,
)

const btnStyle = {
  background: "var(--surface-elevated)",
  borderColor: "var(--border)",
  color: "var(--text-secondary)",
}
const dangerStyle = {
  background: "var(--surface-elevated)",
  borderColor: "var(--status-error)",
  color: "var(--status-error)",
}

function badgeStyle(status: string | null): Record<string, string> {
  if (status === "ok") return { background: "rgba(34,197,94,0.15)", color: "rgb(34,197,94)" }
  if (status === "failed") return { background: "rgba(239,68,68,0.15)", color: "var(--status-error)" }
  return { background: "var(--surface-elevated)", color: "var(--text-tertiary)" }
}

function startCreate() {
  formOpen.value = true
  editingId.value = null
  form.name = ""
  form.base_url = ""
  form.api_key = ""
  form.models = []
  testResult.value = null
}

function startEdit(ep: CustomLLMEndpoint) {
  formOpen.value = true
  editingId.value = ep.id
  form.name = ep.name
  form.base_url = ep.base_url
  form.api_key = "" // nunca pre-preenche
  form.models = [...ep.models]
  testResult.value = null
}

function cancelForm() {
  formOpen.value = false
  editingId.value = null
  testResult.value = null
}

async function testConnection() {
  testing.value = true
  testResult.value = null
  try {
    testResult.value = await testApi(form.base_url, form.api_key || undefined)
    if (testResult.value.success && !form.models.length) {
      // Auto-select all discovered models
      form.models = [...testResult.value.discovered_models]
    }
  } catch (e) {
    testResult.value = {
      success: false,
      error: e instanceof Error ? e.message : "Erro de rede",
      discovered_models: [],
    }
  } finally {
    testing.value = false
  }
}

async function submit() {
  try {
    if (editingId.value) {
      const payload: {
        name: string
        base_url: string
        api_key?: string
        models: CustomLLMModelInfo[]
      } = {
        name: form.name,
        base_url: form.base_url,
        models: form.models,
      }
      if (form.api_key) payload.api_key = form.api_key
      await update(editingId.value, payload)
      toast.add({ title: "Endpoint atualizado", color: "green" })
    } else {
      await create({
        name: form.name,
        base_url: form.base_url,
        api_key: form.api_key || undefined,
        models: form.models,
      })
      toast.add({ title: "Endpoint criado", color: "green" })
    }
    cancelForm()
  } catch (e) {
    toast.add({
      title: "Erro",
      description: e instanceof Error ? e.message : String(e),
      color: "red",
    })
  }
}

async function confirmDelete(ep: CustomLLMEndpoint) {
  if (!confirm(`Deletar endpoint "${ep.name}"?`)) return
  try {
    await remove(ep.id)
    toast.add({ title: "Endpoint deletado", color: "green" })
  } catch (e) {
    toast.add({
      title: "Erro",
      description: e instanceof Error ? e.message : String(e),
      color: "red",
    })
  }
}

async function refreshModels(ep: CustomLLMEndpoint) {
  try {
    await refreshApi(ep.id)
    toast.add({ title: "Models atualizados", color: "green" })
  } catch (e) {
    toast.add({
      title: "Erro",
      description: e instanceof Error ? e.message : String(e),
      color: "red",
    })
  }
}

onMounted(load)
</script>
