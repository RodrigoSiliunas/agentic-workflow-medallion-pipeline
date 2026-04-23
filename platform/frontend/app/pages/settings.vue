<template>
  <div class="flex-1 overflow-y-auto">
    <header
      class="px-6 py-4 border-b"
      :style="{ borderColor: 'var(--border)', background: 'var(--surface)' }"
    >
      <h1 class="text-xl font-semibold">Configurações</h1>
      <p class="text-sm" style="color: var(--text-secondary)">Gerencie credenciais, canais e usuários</p>
    </header>

    <div class="p-6 max-w-3xl space-y-6">
      <!-- Provedor de IA (multi-provider: anthropic / openai / google) -->
      <section>
        <h2 class="text-lg font-semibold mb-1">Provedor de IA</h2>
        <p class="text-xs mb-3" :style="{ color: 'var(--text-tertiary)' }">
          Provider + modelo padrao da empresa. Usado pelo chat agent + Observer.
          Pode ser sobrescrito per-canal/sessao/pipeline.
        </p>

        <!-- Provider radio cards -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-2 mb-3">
          <button
            v-for="p in providers"
            :key="p.id"
            type="button"
            class="text-left px-3 py-2.5 rounded-[var(--radius-md)] border transition-colors"
            :style="providerCardStyle(p.id)"
            @click="handleProviderChange(p.id)"
          >
            <div class="text-sm font-semibold" :style="{ color: 'var(--text-primary)' }">
              {{ p.label }}
            </div>
            <div class="text-[11px] mt-0.5" :style="{ color: 'var(--text-tertiary)' }">
              {{ p.shortDescription }}
            </div>
            <div class="flex gap-1 mt-1.5 flex-wrap">
              <span
                v-if="p.capabilities.tools"
                class="text-[9px] px-1.5 py-0.5 rounded-full"
                :style="{ background: 'rgba(34,197,94,0.15)', color: 'rgb(34,197,94)' }"
              >tools</span>
              <span
                v-if="p.capabilities.vision"
                class="text-[9px] px-1.5 py-0.5 rounded-full"
                :style="{ background: 'rgba(99,102,241,0.15)', color: 'rgb(129,140,248)' }"
              >vision</span>
              <span
                v-if="p.capabilities.promptCaching"
                class="text-[9px] px-1.5 py-0.5 rounded-full"
                :style="{ background: 'rgba(251,191,36,0.15)', color: 'rgb(251,191,36)' }"
              >caching</span>
            </div>
          </button>
        </div>

        <!-- Model dropdown (contextual ao provider selecionado) -->
        <div class="mb-3">
          <label class="block text-xs font-medium mb-1" :style="{ color: 'var(--text-secondary)' }">
            Modelo padrao ({{ selectedProviderLabel }})
          </label>
          <select
            v-model="settings.preferred_model"
            class="w-full px-3 py-2 rounded-[var(--radius-md)] border text-xs"
            :style="{
              background: 'var(--surface)',
              borderColor: 'var(--border)',
              color: 'var(--text-primary)',
            }"
            @change="handleModelChange(settings.preferred_model)"
          >
            <option
              v-for="m in selectedProviderModels"
              :key="m.id"
              :value="m.id"
            >
              {{ m.label }} — {{ formatPrice(m) }}
            </option>
          </select>
        </div>

        <!-- API Keys de cada provider -->
        <div class="space-y-3">
          <CredentialInput
            v-for="cred in aiCredentials"
            :key="cred.type"
            :label="cred.label"
            :type="cred.type"
            :is-configured="settings.credentials[cred.type]?.is_configured"
            :is-valid="settings.credentials[cred.type]?.is_valid"
            @save="(v: string) => handleSave(cred.type, v)"
            @test="() => handleTest(cred.type)"
          />
        </div>
        <p class="text-[10px] mt-2" :style="{ color: 'var(--text-tertiary)' }">
          ⓘ Voce so precisa da chave do provider selecionado. Configure outras
          pra trocar live ou ter fallback futuro.
        </p>
      </section>

      <!-- Infra (AWS + Databricks + GitHub) -->
      <section>
        <h2 class="text-lg font-semibold mb-1">Credenciais de infraestrutura</h2>
        <p class="text-xs mb-3" :style="{ color: 'var(--text-tertiary)' }">
          Defaults da empresa usados em todos os deploys. Voce pode sobrescrever
          credencial-por-credencial no wizard quando criar um deploy especifico.
        </p>
        <div class="space-y-3">
          <CredentialInput
            v-for="cred in infraCredentials"
            :key="cred.type"
            :label="cred.label"
            :type="cred.type"
            :is-configured="settings.credentials[cred.type]?.is_configured"
            :is-valid="settings.credentials[cred.type]?.is_valid"
            @save="(v: string) => handleSave(cred.type, v)"
            @test="() => handleTest(cred.type)"
          />
        </div>
      </section>

      <!-- Databricks Account-level (OAuth M2M, opcional) -->
      <section>
        <h2 class="text-lg font-semibold mb-1">Databricks Account (OAuth M2M)</h2>
        <p class="text-xs mb-2" :style="{ color: 'var(--text-tertiary)' }">
          <strong>Opcional.</strong> Necessario apenas pra modo "criar workspace novo" no wizard.
          Se voce ja tem workspace e prefere fornecer o PAT direto, pode pular esta secao.
        </p>
        <div
          class="p-3 rounded-[var(--radius-md)] mb-3 text-xs space-y-1"
          :style="{
            background: 'rgba(99,102,241,0.08)',
            border: '1px solid rgba(99,102,241,0.25)',
            color: 'var(--text-secondary)',
          }"
        >
          <p class="font-medium" :style="{ color: 'var(--text-primary)' }">
            Como obter:
          </p>
          <ol class="list-decimal pl-5 space-y-0.5">
            <li>Login em <code>accounts.cloud.databricks.com</code></li>
            <li>User management → Service principals → Add service principal (M2M)</li>
            <li>Roles tab → adicionar Account Admin + Metastore Admin</li>
            <li>OAuth secrets tab → Generate secret → copy client_id + secret</li>
            <li>Account ID = UUID na URL ou no canto inferior do Account Console</li>
          </ol>
        </div>
        <div class="space-y-3">
          <CredentialInput
            v-for="cred in databricksAccountCredentials"
            :key="cred.type"
            :label="cred.label"
            :type="cred.type"
            :is-configured="settings.credentials[cred.type]?.is_configured"
            :is-valid="settings.credentials[cred.type]?.is_valid"
            @save="(v: string) => handleSave(cred.type, v)"
            @test="() => handleTest(cred.type)"
          />
        </div>
      </section>


      <!-- Canais -->
      <section>
        <h2 class="text-lg font-semibold mb-3">Canais</h2>
        <div class="space-y-3">
          <CredentialInput
label="Discord Bot Token" type="discord_bot_token"
            :is-configured="settings.credentials.discord_bot_token?.is_configured"
            @save="(v: string) => handleSave('discord_bot_token', v)"
          />
          <CredentialInput
label="Telegram Bot Token" type="telegram_bot_token"
            :is-configured="settings.credentials.telegram_bot_token?.is_configured"
            @save="(v: string) => handleSave('telegram_bot_token', v)"
          />
          <div
            class="p-4 rounded-[var(--radius-lg)]"
            :style="{ background: 'var(--surface)', border: '1px solid var(--border)' }"
          >
            <h3 class="font-medium text-sm mb-2">Canais Omni</h3>
            <p class="text-xs mb-2" :style="{ color: 'var(--text-secondary)' }">
              Gerencie instâncias WhatsApp, Discord e Telegram em um só lugar.
            </p>
            <AppButton variant="outline" size="sm" icon="i-heroicons-phone" to="/channels">
              Abrir Channels
            </AppButton>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
definePageMeta({ layout: "default", middleware: ["role"], role: "admin" })

const toast = useToast()
const { settings, saveCredential, testCredential, updateModel, updateProvider } = useSettings()
const { providers, findProvider, formatPrice } = useLLMProviders()

const aiCredentials = [
  { type: "anthropic_api_key", label: "Anthropic API Key" },
  { type: "openai_api_key", label: "OpenAI API Key" },
  { type: "google_api_key", label: "Google API Key (Gemini)" },
]

const selectedProviderObj = computed(() => findProvider(settings.value.preferred_provider))
const selectedProviderLabel = computed(() => selectedProviderObj.value?.label || "?")
const selectedProviderModels = computed(() => selectedProviderObj.value?.models || [])

function providerCardStyle(id: string): Record<string, string> {
  const isActive = settings.value.preferred_provider === id
  return {
    background: isActive ? "rgba(99,102,241,0.12)" : "var(--surface)",
    borderColor: isActive ? "var(--brand-600)" : "var(--border)",
  }
}

async function handleProviderChange(id: string) {
  await updateProvider(id)
  // Auto-pick primeiro model do provider novo se model atual nao pertence
  const provider = findProvider(id)
  if (provider && !provider.models.find((m) => m.id === settings.value.preferred_model)) {
    const balanced = provider.models.find((m) => m.tier === "balanced") || provider.models[0]
    if (balanced) await updateModel(balanced.id)
  }
  toast.add({ title: `Provider: ${provider?.label}`, color: "green" })
}

const infraCredentials = [
  { type: "aws_access_key_id", label: "AWS Access Key ID" },
  { type: "aws_secret_access_key", label: "AWS Secret Access Key" },
  { type: "aws_region", label: "AWS Region" },
  { type: "databricks_host", label: "Databricks Host URL" },
  { type: "databricks_token", label: "Databricks Token (PAT)" },
  { type: "github_token", label: "GitHub Token" },
  { type: "github_repo", label: "GitHub Repo (owner/repo)" },
]

const databricksAccountCredentials = [
  { type: "databricks_account_id", label: "Databricks Account ID (UUID)" },
  { type: "databricks_oauth_client_id", label: "OAuth Client ID (Service Principal application_id)" },
  { type: "databricks_oauth_secret", label: "OAuth Client Secret" },
]

async function handleSave(type: string, value: string) {
  try {
    await saveCredential(type, value)
    toast.add({ title: "Credencial salva", color: "green" })
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : "Erro desconhecido"
    toast.add({ title: "Erro", description: message, color: "red" })
  }
}

async function handleTest(type: string) {
  const result = await testCredential(type)
  toast.add({
    title: result.success ? "Conexão OK" : "Falhou",
    description: result.message || result.error,
    color: result.success ? "green" : "red",
  })
}

async function handleModelChange(model: string) {
  await updateModel(model)
  toast.add({ title: `Modelo: ${model}`, color: "green" })
}
</script>
