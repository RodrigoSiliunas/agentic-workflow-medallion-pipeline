# AGENTS.md

Instruções para AI agents (Codex, Copilot, Cursor, etc.) trabalhando neste repositório.
Para contexto completo do projeto, consulte `CODEX_MANUAL.md`.

## Monorepo Structure

```
observer-framework/              — Framework reusavel (futuro repo open-source)
  observer/                      — Pacote Python `observer`
    config, dedup, persistence, triggering, validator, workflow_observer
    providers/                   — Factory + registry (anthropic, openai, github)
  notebooks/                     — Notebooks Databricks genericos
    collect_and_fix.py           — Job principal do Observer
    trigger_sentinel.py          — Referenciado pelos workflows dos pipelines
  deploy/create_observer_workflow.py  — Cria o job do Observer
  scripts/update_pr_feedback.py  — CLI da GitHub Action de feedback loop
  templates/                     — dashboard_queries.sql + observer_config.yaml
  tests/                         — 113 testes pytest
  docs/                          — ARCHITECTURE, USAGE, EXTENDING
  README, LICENSE, CHANGELOG, CONTRIBUTING, pyproject.toml

pipelines/                       — Guarda-chuva para multiplos pipelines one-click deploy
  pipeline-seguradora-whatsapp/  — Pipeline WhatsApp de seguro auto (primeiro template)
    notebooks/                   — Databricks notebooks (pre_check, bronze, silver, gold, validation)
    pipeline_lib/                — Biblioteca Python especifica (storage, schema, extractors, masking)
    deploy/                      — Scripts de deploy Databricks (SDK)
    tests/                       — 91 testes pytest
    observer_config.yaml         — Config do Observer para esse deploy
    pyproject.toml

platform/frontend/               — Plataforma Conversacional (Nuxt 4.4.2 + Vue 3)
platform/backend/                — API da Plataforma (FastAPI async)
infra/aws/                       — Terraform (01-foundation, 02-datalake)
conductor/                       — Tracks e workflow do projeto
docs/                            — Análise arquitetural, specs
.github/workflows/               — CI (observer + pipeline) + CD (Databricks sync) + observer-feedback
```

## Zero interdependência entre Observer e Pipeline

O `observer-framework/` e o `pipelines/pipeline-seguradora-whatsapp/` são **dois projetos Python independentes**:

- O pipeline **não importa nada** do framework (`from observer import ...` é proibido em código do pipeline)
- O framework **não importa nada** do pipeline
- O único ponto de contato é o workflow: `deploy/create_workflow.py` do pipeline adiciona uma task `observer_trigger` que referencia o notebook `observer-framework/notebooks/trigger_sentinel` via path absoluto no Databricks Repo

## Pipeline seguradora WhatsApp (pipelines/pipeline-seguradora-whatsapp/)

Pipeline Medallion autônomo: Bronze → Silver → Gold sobre conversas WhatsApp de seguro auto (~153k mensagens).

- **Plataforma**: Databricks Trial (AWS), Unity Catalog, Delta Lake
- **Engine**: PySpark em cluster dedicado (m5d.large) — NÃO serverless
- **Workspace**: `data-capture-engine-prd` em `https://<your-workspace>.cloud.databricks.com`
- **Testes**: 91 testes (pytest), ruff lint
- **Deploy**: Scripts em `pipelines/pipeline-seguradora-whatsapp/deploy/` usando `databricks-sdk`

### Arquitetura ETL

O pipeline ETL é **puro** — zero lógica de agente/AI nos notebooks de dados.
Cada camada faz **overwrite idempotente** — Delta Lake garante atomicidade, sem rollback.
O Observer Agent é um **framework genérico separado** que funciona com qualquer workflow.

```
S3 (Parquet) → [pre_check] → [Bronze] → [Silver x3] → [Gold x12] → [Validation] → [observer_trigger*]
                                                                                          │
                                                                                     *run_if: AT_LEAST_ONE_FAILED
                                                                                          ▼
                                                                                    [Observer Agent]
                                                                                    Claude API → GitHub PR
```

### Workflows Databricks

| Job | ID | Tasks | Schedule |
|-----|----|-------|----------|
| ETL Pipeline | 777105089901314 | 8 tasks (7 ETL + 1 sentinel) | Diário 6 AM SP |
| Observer Agent | 848172838529828 | 1 task (on-demand) | Sem schedule |

### Delta Tables (overwrite idempotente, sem rollback)

- **Catalog**: `medallion` (schemas: bronze, silver, gold)
- Cada notebook faz `overwrite` atômico via Delta Lake
- **Sem rollback Delta** — overwrite idempotente torna rollback desnecessário
- Em caso de falha, `observer_trigger` dispara o Observer para analisar e propor fix via PR

## Observer Framework (observer-framework/)

Framework genérico de observabilidade para qualquer workflow Databricks. Pacote Python `observer`, 113 testes, documentação completa em `observer-framework/docs/`.

### Factory Pattern

```python
from observer.providers import (
    create_llm_provider,    # "anthropic", "openai"
    create_git_provider,    # "github"
    DiagnosisRequest, DiagnosisResult, PRResult,
)
```

- **LLM Providers**: AnthropicProvider (Claude Opus, streaming), OpenAIProvider (GPT-4o)
- **Git Providers**: GitHubProvider (cria branch `fix/agent-auto-*` + PR para `dev`)
- Registry via decorators: `@register_llm_provider("nome")`, `@register_git_provider("nome")`
- Retry com exponential backoff (`@with_retry`) em todas as chamadas externas

Detalhes completos em `observer-framework/README.md` e `observer-framework/docs/ARCHITECTURE.md`.

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
- **02-datalake**: S3 `flowertex-medallion-datalake` com lifecycle rules
- Account ID dinâmico via `data.aws_caller_identity` — NUNCA hardcodar

## CI/CD

- **CI**: 2 jobs separados (observer-framework + pipeline-seguradora-whatsapp), ambos rodam ruff + pytest. Job `validate-agent-pr` roda ambos para branches `fix/*` e `feat/*`.
- **CD**: Sync Databricks Repo com `main` automaticamente. Paths monitorados: `observer-framework/**` e `pipelines/**`.
- **Observer Feedback**: GitHub Action chama `observer-framework/scripts/update_pr_feedback.py` quando PRs `fix/agent-auto-*` são mergeados/fechados.
- **Fluxo**: Observer cria PR para `dev` → CI valida → humano revisa → merge → dev → PR para main → CD deploya.

## Chaos Testing

Injeção controlada de falhas para testar o agente AI end-to-end:

```bash
python pipelines/pipeline-seguradora-whatsapp/deploy/trigger_chaos.py bronze_schema|silver_null|gold_divide_zero|validation_strict
```

## Convenções

- **Commits**: Conventional Commits em pt-BR (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`)
- **Lint Python**: ruff (line-length=100, py311). Notebooks excluídos do lint.
- **Lint JS/TS**: ESLint flat config + Prettier (double quotes, 2 spaces, 100 chars)
- **Testes Python**: pytest. TDD moderado (obrigatório para `observer/` e `pipeline_lib/`, flexível para notebooks)
- **Testes JS**: Vitest + Vue Test Utils
- **Branch strategy**: PRs do agente AI para `dev` (fix/agent-auto-*, feat/*)
- **Dados sensíveis**: Mascaramento na Silver, HMAC obrigatório sem fallback, redaction do message_body
- **Pacotes**: `observer` (framework) e `pipeline_lib` (pipeline WhatsApp). Nunca `lib` — conflita com stdlib Python no Windows
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

## Roadmap — Todas as 8 tracks do Observer COMPLETAS

1. ✅ **Trigger automático** — Task sentinel dispara Observer via `run_if: AT_LEAST_ONE_FAILED`
2. ✅ **Observabilidade** — Tabela `observer.diagnostics` + Dashboard SQL (11 painéis + 3 alerts)
3. ✅ **Deduplicação** — Cache via hash SHA-256 + status do PR no GitHub
4. ✅ **Modo dry-run** — Diagnostica mas NÃO cria PR
5. ✅ **Config como código** — YAML versionado no repo (`observer_config.yaml`)
6. ✅ **Validação pré-PR** — `compile` + `ast.parse` + `ruff` antes do PR
7. ✅ **Multi-file fixes** — `DiagnosisResult.fixes` para N arquivos por PR
8. ✅ **Feedback loop** — GitHub Action atualiza `pr_status` na tabela

### Visão de Produto — One-Click Deploy

Marketplace de pipeline templates com deploy one-click. Terraform programático + Databricks SDK. Atomicidade (saga pattern), idempotência, versionamento de templates, multi-empresa.

## GitHub

- **Monorepo**: `RodrigoSiliunas/agentic-workflow-medallion-pipeline`
- **Observer standalone (privado)**: `RodrigoSiliunas/observer` — placeholder para futura extração do `observer-framework/`
- **Admin email**: `admin@your-domain.com`
