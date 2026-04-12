<template>
  <div class="flex-1 flex flex-col overflow-hidden">
    <!-- Header com back -->
    <header
      class="px-8 py-4 border-b flex items-center gap-3"
      :style="{ borderColor: 'var(--border)' }"
    >
      <AppButton
        variant="ghost"
        size="sm"
        icon="i-heroicons-arrow-left"
        square
        :to="`/marketplace/${template.slug}`"
      />
      <div class="flex-1 min-w-0">
        <h1 class="text-sm font-semibold tracking-tight" :style="{ color: 'var(--text-primary)' }">
          Deploy: {{ template.name }}
        </h1>
        <p class="text-[11px]" :style="{ color: 'var(--text-tertiary)' }">
          Configure as etapas abaixo para provisionar o pipeline na sua conta
        </p>
      </div>
    </header>

    <!-- Step indicator -->
    <div class="px-8 py-5 border-b" :style="{ borderColor: 'var(--border)' }">
      <StepIndicator :steps="stepConfig" :current="currentStep" @select="goToStep" />
    </div>

    <!-- Step content -->
    <div class="flex-1 overflow-y-auto">
      <div class="max-w-2xl mx-auto px-8 py-8">
        <!-- Step 1: Basics -->
        <div v-if="currentStep === 0" class="space-y-4">
          <h2 class="text-base font-semibold mb-1" :style="{ color: 'var(--text-primary)' }">
            Basics
          </h2>
          <p class="text-xs mb-4" :style="{ color: 'var(--text-secondary)' }">
            Identifique seu deployment e escolha o ambiente.
          </p>
          <AppInput
            v-model="config.name"
            label="Nome do deployment"
            placeholder="medallion-whatsapp-prod"
            helper="Nome único que vai identificar esse deploy no dashboard"
          />
          <div>
            <label
              class="block text-xs font-medium mb-1.5"
              :style="{ color: 'var(--text-secondary)' }"
            >
              Ambiente
            </label>
            <div class="grid grid-cols-3 gap-2">
              <button
                v-for="env in environments"
                :key="env.value"
                type="button"
                class="px-3 py-2 rounded-[var(--radius-md)] border text-xs font-medium transition-colors"
                :style="envStyle(env.value)"
                @click="config.environment = env.value"
              >
                {{ env.label }}
              </button>
            </div>
          </div>
          <AppInput
            v-model="tagsText"
            label="Tags (opcional)"
            placeholder="team=data-platform,cost-center=eng"
            helper="Par key=value separado por virgula — aplicado em AWS e Databricks"
          />
        </div>

        <!-- Step 2: Credentials -->
        <div v-else-if="currentStep === 1" class="space-y-3">
          <h2 class="text-base font-semibold mb-1" :style="{ color: 'var(--text-primary)' }">
            Credenciais
          </h2>
          <p class="text-xs mb-3" :style="{ color: 'var(--text-secondary)' }">
            Credenciais configuradas em
            <NuxtLink to="/settings" class="underline" :style="{ color: 'var(--brand-400)' }">/settings</NuxtLink>
            sao usadas automaticamente. Clique em "Sobrescrever" pra usar credenciais
            diferentes apenas neste deploy.
          </p>
          <WizardCredentialField
            v-model="config.credentials.aws_access_key_id"
            label="AWS Access Key ID"
            :company-configured="isCompanyConfigured('aws_access_key_id')"
            placeholder="AKIA..."
            required
          />
          <WizardCredentialField
            v-model="config.credentials.aws_secret_access_key"
            label="AWS Secret Access Key"
            :company-configured="isCompanyConfigured('aws_secret_access_key')"
            input-type="password"
            placeholder="********"
            required
          />
          <WizardCredentialField
            v-model="config.credentials.aws_region"
            label="AWS Region"
            :company-configured="isCompanyConfigured('aws_region')"
            placeholder="us-east-2"
            required
          />
          <WizardCredentialField
            v-model="config.credentials.databricks_host"
            label="Databricks workspace URL"
            :company-configured="isCompanyConfigured('databricks_host')"
            input-type="url"
            placeholder="https://dbc-xxxxx.cloud.databricks.com"
            required
          />
          <WizardCredentialField
            v-model="config.credentials.databricks_token"
            label="Databricks token"
            :company-configured="isCompanyConfigured('databricks_token')"
            input-type="password"
            placeholder="dapi..."
            required
          />
          <WizardCredentialField
            v-model="config.credentials.github_token"
            label="GitHub PAT (para Observer Agent)"
            :company-configured="isCompanyConfigured('github_token')"
            input-type="password"
            placeholder="ghp_..."
          />
        </div>

        <!-- Step 3: Configuration -->
        <div v-else-if="currentStep === 2" class="space-y-4">
          <h2 class="text-base font-semibold mb-1" :style="{ color: 'var(--text-primary)' }">
            Configuração do template
          </h2>
          <p class="text-xs mb-4" :style="{ color: 'var(--text-secondary)' }">
            Variáveis de ambiente específicas deste template.
          </p>
          <AppInput
            v-for="envVar in template.envSchema"
            :key="envVar.key"
            :model-value="config.envVars[envVar.key] ?? envVar.default ?? ''"
            :label="envVar.label + (envVar.required ? ' *' : '')"
            :type="envVar.type === 'password' ? 'password' : 'text'"
            :placeholder="envVar.placeholder"
            :helper="envVar.helper"
            @update:model-value="(v: string) => (config.envVars[envVar.key] = v)"
          />
        </div>

        <!-- Step 4: Review -->
        <div v-else-if="currentStep === 3" class="space-y-4">
          <h2 class="text-base font-semibold mb-1" :style="{ color: 'var(--text-primary)' }">
            Revisão
          </h2>
          <p class="text-xs mb-4" :style="{ color: 'var(--text-secondary)' }">
            Confira as configurações antes de disparar o deploy. Você pode voltar e editar qualquer step.
          </p>

          <section class="rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)]">
            <h3
              class="text-xs font-semibold uppercase tracking-wider px-4 py-2 border-b"
              :style="{ color: 'var(--text-tertiary)', borderColor: 'var(--border)' }"
            >
              Basics
            </h3>
            <dl class="divide-y divide-[var(--border)]">
              <div class="flex justify-between px-4 py-2 text-xs">
                <dt :style="{ color: 'var(--text-tertiary)' }">Nome</dt>
                <dd :style="{ color: 'var(--text-primary)' }">{{ config.name || "—" }}</dd>
              </div>
              <div class="flex justify-between px-4 py-2 text-xs">
                <dt :style="{ color: 'var(--text-tertiary)' }">Ambiente</dt>
                <dd :style="{ color: 'var(--text-primary)' }">{{ config.environment }}</dd>
              </div>
              <div class="flex justify-between px-4 py-2 text-xs">
                <dt :style="{ color: 'var(--text-tertiary)' }">Tags</dt>
                <dd :style="{ color: 'var(--text-primary)' }">
                  {{ tagsText || "—" }}
                </dd>
              </div>
            </dl>
          </section>

          <section class="rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)]">
            <h3
              class="text-xs font-semibold uppercase tracking-wider px-4 py-2 border-b"
              :style="{ color: 'var(--text-tertiary)', borderColor: 'var(--border)' }"
            >
              Credenciais
            </h3>
            <dl class="divide-y divide-[var(--border)]">
              <div
                v-for="key in Object.keys(config.credentials)"
                :key="key"
                class="flex justify-between items-center px-4 py-2 text-xs"
              >
                <dt :style="{ color: 'var(--text-tertiary)' }">{{ key }}</dt>
                <dd class="flex items-center gap-1.5">
                  <template v-if="config.credentials[key]?.trim()">
                    <span
                      class="text-[10px] px-1.5 py-0.5 rounded-full"
                      :style="{ background: 'rgba(251,191,36,0.15)', color: 'rgb(251,191,36)' }"
                    >
                      override
                    </span>
                    <span :style="{ color: 'var(--text-primary)' }">
                      {{ maskValue(config.credentials[key] ?? '') }}
                    </span>
                  </template>
                  <template v-else-if="isCompanyConfigured(key)">
                    <AppIcon name="check-circle" size="xs" :style="{ color: 'var(--brand-400)' }" />
                    <span :style="{ color: 'var(--brand-400)' }">Credencial da empresa</span>
                  </template>
                  <template v-else>
                    <span :style="{ color: 'var(--status-error)' }">— faltando</span>
                  </template>
                </dd>
              </div>
            </dl>
          </section>

          <section class="rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)]">
            <h3
              class="text-xs font-semibold uppercase tracking-wider px-4 py-2 border-b"
              :style="{ color: 'var(--text-tertiary)', borderColor: 'var(--border)' }"
            >
              Env vars do template
            </h3>
            <dl class="divide-y divide-[var(--border)]">
              <div
                v-for="envVar in template.envSchema"
                :key="envVar.key"
                class="flex justify-between px-4 py-2 text-xs"
              >
                <dt :style="{ color: 'var(--text-tertiary)' }">{{ envVar.label }}</dt>
                <dd :style="{ color: 'var(--text-primary)' }">
                  {{
                    envVar.type === "password"
                      ? maskValue(config.envVars[envVar.key] ?? "")
                      : config.envVars[envVar.key] || envVar.default || "—"
                  }}
                </dd>
              </div>
            </dl>
          </section>

          <label class="flex items-start gap-2 text-xs" :style="{ color: 'var(--text-secondary)' }">
            <input v-model="confirmed" type="checkbox" class="mt-0.5 accent-[var(--brand-600)]">
            <span>
              Confirmo que as credenciais acima são válidas e autorizo o provisionamento de
              recursos na minha conta AWS e Databricks. Este deployment cria buckets S3, IAM roles
              e workflows.
            </span>
          </label>
        </div>
      </div>
    </div>

    <!-- Footer actions -->
    <footer
      class="px-8 py-4 border-t flex items-center justify-between gap-3"
      :style="{ borderColor: 'var(--border)', background: 'var(--surface)' }"
    >
      <AppButton
        v-if="currentStep > 0"
        variant="ghost"
        size="sm"
        icon="i-heroicons-arrow-left"
        @click="currentStep--"
      >
        Voltar
      </AppButton>
      <div v-else />
      <div class="flex items-center gap-2">
        <AppButton variant="outline" size="sm" :to="`/marketplace/${template.slug}`">
          Cancelar
        </AppButton>
        <AppButton
          v-if="currentStep < stepConfig.length - 1"
          size="sm"
          trailing-icon="i-heroicons-arrow-right"
          :disabled="!canAdvance"
          @click="currentStep++"
        >
          Próximo
        </AppButton>
        <AppButton
          v-else
          size="sm"
          icon="i-heroicons-rocket-launch"
          :disabled="!confirmed"
          @click="handleDeploy"
        >
          Deploy agora
        </AppButton>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import type { Template } from "~/types/template"
import type { DeploymentConfig } from "~/types/deployment"

const props = defineProps<{ template: Template }>()

const deploymentsStore = useDeploymentsStore()

const stepConfig = [
  { key: "basics", label: "Basics" },
  { key: "credentials", label: "Credenciais" },
  { key: "config", label: "Config" },
  { key: "review", label: "Revisão" },
]

const environments: Array<{ value: "dev" | "staging" | "prod"; label: string }> = [
  { value: "dev", label: "Dev" },
  { value: "staging", label: "Staging" },
  { value: "prod", label: "Prod" },
]

const currentStep = ref(0)
const confirmed = ref(false)
const tagsText = ref("team=data-platform,company=safatechx")

const config = reactive<DeploymentConfig>({
  name: `${props.template.slug}-prod`,
  environment: "prod",
  tags: {},
  credentials: {
    aws_access_key_id: "",
    aws_secret_access_key: "",
    aws_region: "",
    databricks_host: "",
    databricks_token: "",
    github_token: "",
  },
  envVars: {},
})

// Busca credenciais ja configuradas em /settings pra permitir pre-fill
// + override per-deploy. O backend NAO retorna os valores (so o status),
// entao a gente so usa pra saber se o campo no wizard pode ser opcional.
const { settings } = useSettings()
function isCompanyConfigured(credType: string): boolean {
  const entry = settings.value.credentials[credType] as
    | { is_configured?: boolean }
    | undefined
  return Boolean(entry?.is_configured)
}

// Pre-fill env vars with defaults
for (const envVar of props.template.envSchema) {
  if (envVar.default) config.envVars[envVar.key] = envVar.default
}

const REQUIRED_CRED_TYPES = [
  "aws_access_key_id",
  "aws_secret_access_key",
  "aws_region",
  "databricks_host",
  "databricks_token",
] as const

const canAdvance = computed(() => {
  if (currentStep.value === 0) return config.name.trim().length > 0
  if (currentStep.value === 1) {
    // Pra cada credencial obrigatoria: passa se a empresa tem configurada
    // OU se o user digitou um override no wizard.
    return REQUIRED_CRED_TYPES.every(
      (t) => isCompanyConfigured(t) || !!config.credentials[t]?.trim(),
    )
  }
  if (currentStep.value === 2) {
    return props.template.envSchema.every(
      (e) => !e.required || (config.envVars[e.key] ?? e.default ?? "").trim().length > 0,
    )
  }
  return true
})

function envStyle(value: string): Record<string, string> {
  const isActive = config.environment === value
  return {
    background: isActive ? "var(--brand-600)" : "var(--surface)",
    color: isActive ? "white" : "var(--text-secondary)",
    borderColor: isActive ? "var(--brand-600)" : "var(--border)",
  }
}

function goToStep(idx: number) {
  if (idx < currentStep.value) currentStep.value = idx
}

function maskValue(value: string): string {
  if (!value) return "—"
  if (value.length <= 4) return "****"
  return `${value.slice(0, 2)}${"*".repeat(Math.min(value.length - 4, 12))}${value.slice(-2)}`
}

async function handleDeploy() {
  // parsear tags
  const parsed: Record<string, string> = {}
  for (const pair of tagsText.value.split(",")) {
    const [k, v] = pair.split("=").map((s) => s.trim())
    if (k && v) parsed[k] = v
  }
  config.tags = parsed

  // So envia credenciais que tem valor — strings vazias sinalizam pro
  // backend "use a credencial da empresa". Isso evita que o usuario mande
  // "" sobrescrevendo a credencial legitima do /settings com vazio.
  const overrideCreds: Record<string, string> = {}
  for (const [key, value] of Object.entries(config.credentials)) {
    if (value && value.trim()) overrideCreds[key] = value.trim()
  }

  const deployment = await deploymentsStore.createDeployment(
    props.template.slug,
    props.template.name,
    { ...config, credentials: overrideCreds, envVars: { ...config.envVars } },
  )

  navigateTo(`/deployments/${deployment.id}`)
  // dispara saga em background (nao espera)
  deploymentsStore.runSaga(deployment.id)
}
</script>
