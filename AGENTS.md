# AGENTS.md

Instruções para AI agents (Codex, Copilot, Cursor, etc.) trabalhando neste repositório.
Para contexto completo do projeto, consulte `CODEX_MANUAL.md`.

## Monorepo Structure

```
pipeline/                        — Pipeline Medallion (Databricks + AWS)
  notebooks/                     — Databricks notebooks (.py source format)
    agent_pre.py                 — Task 0: fingerprint S3, captura versões Delta
    bronze/ingest.py             — Task 1: S3 parquet → Delta bronze
    silver/dedup_clean.py        — Task 2: dedup + normalização
    silver/entities_mask.py      — Task 3: extração entidades + mascaramento PII
    silver/enrichment.py         — Task 4: métricas conversacionais
    gold/analytics.py            — Task 5: orquestrador (12 notebooks em paralelo)
    gold/*.py                    — 12 notebooks analíticos (funnel, sentiment, etc.)
    validation/checks.py         — Task 6: quality gates (row counts, nulls, consistency)
    agent_post.py                — Task 7: rollback Delta + trigger Observer
    observer/collect_and_fix.py  — Notebook do Observer Agent (job separado)
  pipeline_lib/                  — Biblioteca Python compartilhada
    agent/observer/              — Framework Observer Agent (factory pattern)
    storage/s3_client.py         — S3Lake: leitura/escrita S3 via boto3 in-memory
    schema/                      — Contratos de schema + validador
    extractors/                  — Extratores de entidades (CPF, phone, email, etc.)
    masking/                     — Mascaramento PII (HMAC, redaction, format-preserving)
  deploy/                        — Scripts de deploy Databricks (SDK)
  tests/                         — 89 testes pytest
platform/frontend/               — Plataforma Conversacional (Nuxt 4.4.2 + Vue 3)
platform/backend/                — API da Plataforma (FastAPI async)
infra/aws/                       — Terraform (01-foundation, 02-datalake)
conductor/                       — Tracks e workflow do projeto
docs/                            — Análise arquitetural, specs
.github/workflows/               — CI (ruff + pytest) + CD (Databricks sync)
```

## Pipeline (pipeline/)

Pipeline Medallion autônomo: Bronze → Silver → Gold sobre conversas WhatsApp de seguro auto (~153k mensagens).

- **Plataforma**: Databricks Trial (AWS), Unity Catalog, Delta Lake
- **Engine**: PySpark em cluster dedicado (m5d.large) — NÃO serverless
- **Workspace**: `data-capture-engine-prd` em `https://dbc-1bad7a6a-cc31.cloud.databricks.com`
- **Testes**: 89 testes (pytest), ruff lint
- **Deploy**: Scripts em `pipeline/deploy/` usando `databricks-sdk`

### Arquitetura ETL

O pipeline ETL é **puro** — zero lógica de agente/AI nos notebooks de dados.
O Observer Agent é um **framework genérico separado** que funciona com qualquer workflow.

```
S3 (Parquet) → [agent_pre] → [Bronze] → [Silver x3] → [Gold x12] → [Validation] → [agent_post]
                                                                                         │
                                                                                    (se falhou)
                                                                                         ▼
                                                                                    [Observer Agent]
                                                                                    Claude API → GitHub PR
```

### Workflows Databricks

| Job | ID | Tasks | Schedule |
|-----|----|-------|----------|
| ETL Pipeline | 777105089901314 | 8 tasks sequenciais | Diário 6 AM SP |
| Observer Agent | 848172838529828 | 1 task (on-demand) | Sem schedule |

### Delta Tables e Rollback

- **Catalog**: `medallion` (schemas: bronze, silver, gold)
- Cada notebook faz `overwrite` atômico via Delta Lake
- `agent_pre` captura versões Delta de 17 tabelas antes da execução
- `agent_post` faz `RESTORE TABLE ... TO VERSION AS OF` se pipeline falhar
- Rollback (dados) + Observer/AI (código) são complementares e sempre executam juntos

## Observer Agent Framework (pipeline_lib/agent/observer/)

Framework genérico de observabilidade para qualquer workflow Databricks.

### Factory Pattern

```python
from pipeline_lib.agent.observer.providers import (
    create_llm_provider,    # "anthropic", "openai"
    create_git_provider,    # "github"
    DiagnosisRequest, DiagnosisResult, PRResult,
)
```

- **LLM Providers**: AnthropicProvider (Claude Opus, streaming), OpenAIProvider (GPT-4o)
- **Git Providers**: GitHubProvider (cria branch `fix/agent-auto-*` + PR para `dev`)
- Registry via decorators: `@register_llm_provider("nome")`, `@register_git_provider("nome")`
- Retry com exponential backoff (`@with_retry`) em todas as chamadas externas

## Platform Frontend (platform/frontend/)

- **Framework**: Nuxt 4.4.2 + Vue 3 + TypeScript
- **Package manager**: Bun
- **UI**: @nuxt/ui (Tailwind-based)
- **Estado**: Pinia
- **Composables**: @vueuse/nuxt
- **Arquitetura**: Atomic Design (`atoms/` → `molecules/` → `organisms/` → `templates/`)
- **Padrões idlehub**: useApiClient com token refresh, SWR caching, auth middleware global

## Platform Backend (platform/backend/)

- **Framework**: FastAPI (async)
- **Auth**: JWT + API Key, RBAC (viewer/editor/admin), multi-tenant
- **DB**: PostgreSQL (SQLAlchemy 2 async)
- **Cache**: Redis
- **Padrões**: Service layer, domain exceptions, Pydantic Settings, lifespan hooks

## Infraestrutura (infra/aws/)

- **01-foundation**: IAM users/roles/policies, Security Groups, Secrets Manager, S3 Databricks root
- **02-datalake**: S3 `namastex-medallion-datalake` com lifecycle rules
- Account ID dinâmico via `data.aws_caller_identity` — NUNCA hardcodar

## CI/CD

- **CI**: ruff + pytest em push para main/dev e PRs. Job extra para branches `fix/*` e `feat/*`.
- **CD**: Sync Databricks Repo com `main` automaticamente em push.
- **Fluxo**: Observer cria PR para `dev` → CI valida → humano revisa → merge → dev → PR para main → CD deploya.

## Chaos Testing

Injeção controlada de falhas para testar o agente AI end-to-end:

```bash
python pipeline/deploy/trigger_chaos.py bronze_schema|silver_null|gold_divide_zero|validation_strict
```

## Convenções

- **Commits**: Conventional Commits em pt-BR (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`)
- **Lint Python**: ruff (line-length=100, py311). Notebooks excluídos do lint.
- **Lint JS/TS**: ESLint flat config + Prettier (double quotes, 2 spaces, 100 chars)
- **Testes Python**: pytest. TDD moderado (obrigatório para pipeline_lib/, flexível para notebooks)
- **Testes JS**: Vitest + Vue Test Utils
- **Branch strategy**: PRs do agente AI para `dev` (fix/agent-auto-*, feat/*)
- **Dados sensíveis**: Mascaramento na Silver, HMAC obrigatório sem fallback, redaction do message_body
- **Pacote**: `pipeline_lib` (NÃO `lib` — conflita com stdlib Python no Windows)
- **Schema evolution**: Colunas novas aceitas via Delta `mergeSchema`, nunca rejeitadas
- **Deploy scripts**: Sempre parametrizados via env vars, nunca hardcoded

### Padrão de Notebooks Databricks

1. **Header markdown** como primeira célula (`# MAGIC %md`)
2. **DBTITLE** em TODA célula de código (`# DBTITLE 1,Nome`), NÃO em células %md separadas
3. **Imports** na primeira célula de código: `from...import` primeiro (alfabético), depois `import` (alfabético)
4. **SEM inline imports** — tudo no topo do notebook
5. **Comentários** frequentes em PT-BR com acentuação correta
6. **`dbutils.notebook.exit()`** NUNCA dentro de try/except
7. Separador entre células: `# COMMAND ----------`

## Roadmap — Melhorias Aprovadas

### Observer Agent (8 melhorias, em ordem de prioridade)

1. **Trigger automático** — Webhook/task final dispara Observer imediatamente
2. **Observabilidade** — Tabela `observer.diagnostics` + Dashboard SQL
3. **Deduplicação** — Cache de diagnósticos (hash do erro), evita PRs duplicados
4. **Modo dry-run** — Diagnostica mas NÃO cria PR
5. **Config como código** — YAML/JSON no repo ao invés de widgets
6. **Validação pré-PR** — ruff + pytest antes de criar PR
7. **Multi-file fixes** — LLM propõe changes em N arquivos
8. **Feedback loop** — Webhook GitHub notifica merge/close de PRs

### Visão de Produto — One-Click Deploy

Marketplace de pipeline templates com deploy one-click. Terraform programático + Databricks SDK. Atomicidade (saga pattern), idempotência, versionamento de templates, multi-empresa.

## GitHub

- **Repo**: `RodrigoSiliunas/agentic-workflow-medallion-pipeline`
- **Admin email**: `administrator@idlehub.com.br`
