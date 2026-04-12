<template>
  <div class="flex-1 overflow-y-auto">
    <header
      class="px-6 py-4 border-b"
      :style="{ borderColor: 'var(--border)', background: 'var(--surface)' }"
    >
      <h1 class="text-xl font-semibold" :style="{ color: 'var(--text-primary)' }">
        Central de Ajuda
      </h1>
      <p class="text-sm" :style="{ color: 'var(--text-secondary)' }">
        Tudo que voce precisa saber para fazer o deploy do seu primeiro pipeline.
      </p>
    </header>

    <div class="p-6 max-w-3xl space-y-8">
      <!-- Quick Start -->
      <section>
        <h2 class="help-title">
          <AppIcon name="rocket-launch" size="md" class="text-[var(--brand-500)]" />
          Quick Start (5 minutos)
        </h2>
        <ol class="help-steps">
          <li>
            <strong>Crie sua conta</strong> em
            <NuxtLink to="/register" class="help-link">/register</NuxtLink>
            com o nome da empresa e um email valido.
          </li>
          <li>
            <strong>Configure as credenciais</strong> em
            <NuxtLink to="/settings" class="help-link">/settings</NuxtLink>.
            Voce precisa de: AWS Access Key, Databricks Token, e GitHub Token (classic).
          </li>
          <li>
            <strong>Escolha um template</strong> no
            <NuxtLink to="/marketplace" class="help-link">Marketplace</NuxtLink>
            e clique em "Deploy".
          </li>
          <li>
            <strong>Preencha o wizard</strong> (4 steps) — as credenciais da empresa
            sao pre-preenchidas automaticamente.
          </li>
          <li>
            <strong>Acompanhe o deploy</strong> em tempo real na pagina de detalhes.
            O pipeline inteiro e provisionado em ~30 segundos.
          </li>
        </ol>
      </section>

      <!-- Requisitos -->
      <section>
        <h2 class="help-title">
          <AppIcon name="clipboard-document-check" size="md" class="text-[var(--brand-500)]" />
          Pre-requisitos
        </h2>
        <div class="space-y-4">
          <HelpRequisite
            title="Conta AWS"
            description="Conta AWS com permissao pra criar S3 buckets, IAM roles, e Secrets Manager secrets."
            :items="[
              'AWS Access Key ID (formato: AKIA...)',
              'AWS Secret Access Key',
              'Regiao: us-east-2 (recomendado) ou qualquer regiao suportada pelo Databricks',
            ]"
            link="https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_access-keys.html"
            link-text="Como criar Access Keys na AWS"
          />

          <HelpRequisite
            title="Workspace Databricks"
            description="Workspace Databricks com Unity Catalog habilitado e um SQL Warehouse disponivel."
            :items="[
              'Databricks Host URL (formato: https://dbc-xxxxx.cloud.databricks.com)',
              'Personal Access Token (formato: dapi...)',
              'SQL Warehouse ativo (Starter ou Pro — o deploy inicia automaticamente se estiver parado)',
            ]"
            link="https://docs.databricks.com/en/dev-tools/auth/pat.html"
            link-text="Como gerar um Databricks PAT"
          />

          <HelpRequisite
            title="GitHub Token (Classic)"
            description="Token de acesso pessoal do GitHub para clonar o repositorio do pipeline no Databricks."
            :items="[
              'Tipo: Classic PAT (comeca com ghp_). Fine-grained tokens (github_pat_) NAO funcionam com Databricks.',
              'Scope minimo: repo (acesso completo a repositorios privados)',
              'O token e usado para: (1) clonar o repo no Databricks, (2) Observer Agent abrir PRs com fixes automaticos',
            ]"
            link="https://github.com/settings/tokens"
            link-text="Gerar Classic PAT no GitHub"
            warning="Fine-grained tokens (github_pat_*) nao sao suportados pelo Databricks Repos API. Use exclusivamente o Classic PAT (ghp_*)."
          />

          <HelpRequisite
            title="Anthropic API Key (opcional)"
            description="Chave da API Anthropic para o Observer Agent diagnosticar falhas automaticamente usando Claude."
            :items="[
              'Formato: sk-ant-api03-...',
              'Usado apenas pelo Observer Agent — o pipeline ETL funciona sem ele',
              'Modelo usado: Claude Opus (streaming obrigatorio)',
            ]"
            link="https://console.anthropic.com/settings/keys"
            link-text="Gerar API Key na Anthropic"
          />
        </div>
      </section>

      <!-- Credenciais -->
      <section>
        <h2 class="help-title">
          <AppIcon name="key" size="md" class="text-[var(--brand-500)]" />
          Onde configurar credenciais
        </h2>
        <div class="help-card">
          <p class="text-sm mb-3" :style="{ color: 'var(--text-secondary)' }">
            Existem dois lugares para configurar credenciais:
          </p>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div class="help-subcard">
              <h4 class="text-xs font-semibold uppercase tracking-wider mb-2" :style="{ color: 'var(--brand-400)' }">
                /settings (empresa)
              </h4>
              <p class="text-xs" :style="{ color: 'var(--text-secondary)' }">
                Credenciais globais da empresa. Configuradas uma vez e reutilizadas em
                todos os deploys. Recomendado para AWS, Databricks, GitHub e Anthropic.
              </p>
            </div>
            <div class="help-subcard">
              <h4 class="text-xs font-semibold uppercase tracking-wider mb-2" :style="{ color: 'var(--brand-400)' }">
                Wizard (por deploy)
              </h4>
              <p class="text-xs" :style="{ color: 'var(--text-secondary)' }">
                Override por deploy. Se a credencial ja esta em /settings, o wizard
                mostra "Usando credencial da empresa" e voce avanca sem digitar.
                Clique em "Sobrescrever" para usar valores diferentes naquele deploy especifico.
              </p>
            </div>
          </div>
        </div>
      </section>

      <!-- Etapas do Deploy -->
      <section>
        <h2 class="help-title">
          <AppIcon name="list-bullet" size="md" class="text-[var(--brand-500)]" />
          O que o deploy faz (10 etapas)
        </h2>
        <div class="help-card space-y-3">
          <HelpStep number="1" title="Validate Credentials" duration="~1s">
            Verifica AWS STS, Databricks workspace, Anthropic e GitHub.
            Credenciais opcionais (Anthropic, GitHub) geram apenas warning.
          </HelpStep>
          <HelpStep number="2" title="Create S3 Bucket" duration="~1-5s">
            Verifica se o bucket existe. Se nao, cria com versionamento,
            encryption AES256 e acesso publico bloqueado.
          </HelpStep>
          <HelpStep number="3" title="Provision IAM Role" duration="~1-3s">
            Verifica/cria a IAM role cross-account para Databricks acessar o S3.
          </HelpStep>
          <HelpStep number="4" title="Create Secrets Scope" duration="~2s">
            Cria o scope de secrets no Databricks e armazena AWS keys,
            Anthropic key, GitHub token, e masking secret.
          </HelpStep>
          <HelpStep number="5" title="Setup Unity Catalog" duration="~2-30s">
            Cria o catalog + schemas (bronze, silver, gold, pipeline, observer).
            Se o SQL Warehouse estiver parado, inicia automaticamente (~2min cold start).
          </HelpStep>
          <HelpStep number="6" title="Upload Notebooks" duration="~4s">
            Clona o repositorio GitHub no Databricks via Repos API.
            Requer Classic PAT (ghp_*).
          </HelpStep>
          <HelpStep number="7" title="Deploy Observer Agent" duration="~1s">
            Cria o job on-demand do Observer Agent (diagnostico autonomo de falhas).
          </HelpStep>
          <HelpStep number="8" title="Create Workflow" duration="~1s">
            Cria o job ETL com 8 tasks em DAG: pre_check, bronze, silver (x3),
            gold, validation, observer_trigger.
          </HelpStep>
          <HelpStep number="9" title="Trigger First Run" duration="~10s-20min">
            Dispara o primeiro run e acompanha ate concluir. Falhas no pipeline
            nao fazem o deploy falhar — o Observer Agent e acionado automaticamente.
          </HelpStep>
          <HelpStep number="10" title="Register in Platform" duration="~0s">
            Registra o pipeline no dashboard. O chat agent ja pode conversar
            sobre o workflow.
          </HelpStep>
        </div>
      </section>

      <!-- Troubleshooting -->
      <section>
        <h2 class="help-title">
          <AppIcon name="wrench-screwdriver" size="md" class="text-[var(--brand-500)]" />
          Solucao de problemas
        </h2>
        <div class="space-y-3">
          <HelpTroubleshoot
            error="GitHub: PermissionDenied / Access not granted"
            solution="Voce esta usando um Fine-grained token (github_pat_*). Gere um Classic PAT (ghp_*) com scope 'repo' em github.com/settings/tokens."
          />
          <HelpTroubleshoot
            error="S3: Access Denied / 403 Forbidden"
            solution="O IAM user nao tem permissao pra criar buckets. Verifique que a Access Key tem policies de S3 (PutObject, CreateBucket, etc)."
          />
          <HelpTroubleshoot
            error="Databricks: Authorization header is invalid"
            solution="Token Databricks expirado ou invalido. Gere um novo em User Settings > Developer > Access Tokens no workspace."
          />
          <HelpTroubleshoot
            error="Catalog: Metastore storage root URL does not exist"
            solution="O metastore trial nao tem storage root configurado. O deploy cria automaticamente um Storage Credential + External Location. Se falhar, verifique que a IAM role tem acesso ao S3 bucket."
          />
          <HelpTroubleshoot
            error="Workflow: Invalid quartz_cron_expression"
            solution="O schedule usa Quartz cron (6 campos), nao Unix cron (5 campos). Formato: '0 0 6 * * ?' (segundos minutos hora dia mes dia-da-semana). O deploy converte automaticamente."
          />
          <HelpTroubleshoot
            error="Pipeline run: INTERNAL_ERROR"
            solution="O pipeline foi provisionado mas os dados de entrada (parquet no S3) podem nao existir ainda. Faca upload dos dados em s3://bucket/bronze/ e re-trigger o job no Databricks."
          />
        </div>
      </section>

      <!-- Arquitetura -->
      <section>
        <h2 class="help-title">
          <AppIcon name="cube-transparent" size="md" class="text-[var(--brand-500)]" />
          Arquitetura
        </h2>
        <div class="help-card">
          <pre class="text-[11px] leading-relaxed overflow-x-auto" :style="{ color: 'var(--text-secondary)' }">
S3 (Parquet) -> [pre_check] -> [Bronze] -> [Silver x3] -> [Gold x12] -> [Validation]
                                                                              |
                                                                     run_if: AT_LEAST_ONE_FAILED
                                                                              |
                                                                              v
                                                                       [Observer Agent]
                                                                       Claude API -> GitHub PR
          </pre>
          <ul class="mt-3 space-y-1 text-xs" :style="{ color: 'var(--text-secondary)' }">
            <li>
              <strong>Bronze</strong>: S3 parquet -> Delta Lake (overwrite idempotente)
            </li>
            <li>
              <strong>Silver</strong>: Dedup + mascaramento PII (HMAC) + enrichment conversacional
            </li>
            <li>
              <strong>Gold</strong>: 12 tabelas analiticas (funnel, sentiment, NPS, handle_time)
            </li>
            <li>
              <strong>Observer</strong>: Claude Opus diagnostica falhas + cria PR no GitHub automaticamente
            </li>
          </ul>
        </div>
      </section>

      <!-- Links uteis -->
      <section class="pb-8">
        <h2 class="help-title">
          <AppIcon name="link" size="md" class="text-[var(--brand-500)]" />
          Links uteis
        </h2>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
          <a
            v-for="link in externalLinks"
            :key="link.url"
            :href="link.url"
            target="_blank"
            rel="noopener"
            class="help-subcard flex items-center gap-3 hover:border-[var(--brand-500)]/40 transition-colors"
          >
            <AppIcon :name="link.icon" size="md" :style="{ color: link.color }" />
            <div>
              <p class="text-xs font-medium" :style="{ color: 'var(--text-primary)' }">
                {{ link.title }}
              </p>
              <p class="text-[10px]" :style="{ color: 'var(--text-tertiary)' }">
                {{ link.description }}
              </p>
            </div>
          </a>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
definePageMeta({ layout: "default" })

const externalLinks = [
  {
    title: "AWS Console",
    description: "IAM, S3, Secrets Manager",
    url: "https://console.aws.amazon.com",
    icon: "cloud",
    color: "var(--status-warning)",
  },
  {
    title: "Databricks Workspace",
    description: "Jobs, Repos, SQL Warehouses",
    url: "https://accounts.cloud.databricks.com",
    icon: "cpu-chip",
    color: "var(--status-error)",
  },
  {
    title: "GitHub Tokens",
    description: "Gerar Classic PAT (ghp_*)",
    url: "https://github.com/settings/tokens",
    icon: "i-simple-icons-github",
    color: "var(--text-primary)",
  },
  {
    title: "Anthropic Console",
    description: "API Keys para Claude",
    url: "https://console.anthropic.com",
    icon: "sparkles",
    color: "var(--brand-500)",
  },
]
</script>

<style scoped>
.help-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1rem;
  font-weight: 600;
  margin-bottom: 0.75rem;
  color: var(--text-primary);
}

.help-steps {
  list-style: decimal;
  padding-left: 1.25rem;
  space-y: 0.5rem;
}

.help-steps li {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  padding: 0.25rem 0;
}

.help-link {
  color: var(--brand-400);
  text-decoration: underline;
  text-underline-offset: 2px;
}

.help-card {
  padding: 1rem;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
  background: var(--surface);
}

.help-subcard {
  padding: 0.75rem;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--surface-elevated);
}
</style>
