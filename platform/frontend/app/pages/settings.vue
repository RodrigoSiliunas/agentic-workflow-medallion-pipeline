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
      <!-- IA -->
      <section>
        <h2 class="text-lg font-semibold mb-1">Provedor de IA</h2>
        <p class="text-xs mb-3" :style="{ color: 'var(--text-tertiary)' }">
          Chave Claude usada pelo Observer Agent pra diagnosticar falhas e abrir PRs.
        </p>
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

      <!-- Modelo LLM -->
      <section>
        <h2 class="text-lg font-semibold mb-3">Modelo LLM</h2>
        <div
          class="p-4 rounded-[var(--radius-lg)]"
          :style="{ background: 'var(--surface)', border: '1px solid var(--border)' }"
        >
          <p class="text-sm mb-3" :style="{ color: 'var(--text-secondary)' }">Modelo preferido para sua empresa</p>
          <div class="flex gap-3">
            <UButton
              :variant="settings.preferred_model === 'sonnet' ? 'solid' : 'outline'"
              @click="handleModelChange('sonnet')"
            >
              Sonnet (rápido)
            </UButton>
            <UButton
              :variant="settings.preferred_model === 'opus' ? 'solid' : 'outline'"
              @click="handleModelChange('opus')"
            >
              Opus (inteligente)
            </UButton>
          </div>
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
const { settings, saveCredential, testCredential, updateModel } = useSettings()

const aiCredentials = [
  { type: "anthropic_api_key", label: "Anthropic API Key" },
]

const infraCredentials = [
  { type: "aws_access_key_id", label: "AWS Access Key ID" },
  { type: "aws_secret_access_key", label: "AWS Secret Access Key" },
  { type: "aws_region", label: "AWS Region" },
  { type: "databricks_host", label: "Databricks Host URL" },
  { type: "databricks_token", label: "Databricks Token" },
  { type: "github_token", label: "GitHub Token" },
  { type: "github_repo", label: "GitHub Repo (owner/repo)" },
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
