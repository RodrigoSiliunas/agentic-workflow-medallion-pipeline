# CLAUDE.md

Instruções para AI assistants (Claude Code, Codex, etc.) neste repo.

## Monorepo Structure

```
observer-framework/              — Framework reusavel (futuro repo open-source privado em RodrigoSiliunas/observer)
  observer/                      — Pacote Python `observer`
    config.py                    — ObserverConfig + load_observer_config (YAML + overrides)
    dedup.py                     — check_duplicate via hash SHA-256 + status do PR
    persistence.py               — ObserverDiagnosticsStore (Delta table de observabilidade)
    triggering.py                — Helpers do task sentinel
    validator.py                 — validate_fix (compile + ast + ruff pre-PR)
    workflow_observer.py         — Coleta contexto via APIs do Databricks
    providers/                   — Factory + registry (anthropic, openai, github)
  notebooks/                     — Notebooks Databricks genericos
    collect_and_fix.py           — Job principal do Observer (Jobs API + LLM + PR)
    trigger_sentinel.py          — Task referenciada pelos workflows dos pipelines
  deploy/create_observer_workflow.py  — Cria o job do Observer no Databricks
  scripts/update_pr_feedback.py  — CLI chamado pela GitHub Action do feedback loop
  templates/                     — dashboard_queries.sql + observer_config.yaml
  tests/                         — 113 testes pytest (config, dedup, persistence, providers, etc.)
  docs/                          — ARCHITECTURE.md, USAGE.md, EXTENDING.md
  README.md, LICENSE, CHANGELOG.md, CONTRIBUTING.md, pyproject.toml

pipelines/                       — Guarda-chuva para multiplos pipelines one-click deploy
  pipeline-seguradora-whatsapp/  — Pipeline WhatsApp de seguro auto (primeiro template)
    notebooks/                   — Databricks notebooks (.py source format)
      pre_check.py               — Task 0: pre-flight (propaga run_id + chaos_mode)
      bronze/ingest.py           — Task 1: S3 parquet → Delta bronze (overwrite)
      silver/dedup_clean.py      — Task 2: dedup + normalização
      silver/entities_mask.py    — Task 3: extração entidades + mascaramento PII
      silver/enrichment.py       — Task 4: métricas conversacionais
      gold/analytics.py          — Task 5: orquestrador (12 notebooks em paralelo)
      gold/*.py                  — 12 notebooks analíticos (funnel, sentiment, etc.)
      validation/checks.py       — Task 6: quality gates (row counts, nulls, consistency)
    pipeline_lib/                — Biblioteca Python especifica WhatsApp
      storage/s3_client.py       — S3Lake: leitura/escrita S3 via boto3 in-memory
      schema/                    — Contratos de schema + validador
      extractors/                — Extratores de entidades (CPF, phone, email, etc.)
      masking/                   — Mascaramento PII (HMAC, redaction, format-preserving)
    deploy/                      — Scripts de deploy Databricks (SDK)
      create_workflow.py         — Cria o workflow ETL; task sentinel referencia o notebook do observer-framework via path
      setup_catalog.py, trigger_chaos.py, trigger_run.py, upload_data.py
    tests/                       — 91 testes pytest (extractors, masking, schema, deploy)
    data/conversations_bronze.parquet  — Dados de sample (gitignored)
    observer_config.yaml         — Config do Observer para esse deploy especifico
    pyproject.toml

platform/frontend/               — Plataforma Conversacional (Nuxt 4.4.2 + Vue 3)
platform/backend/                — API da Plataforma (FastAPI async)
platform/design/                 — Design system references
infra/aws/                       — Terraform (01-foundation, 02-datalake)
conductor/                       — Tracks e workflow do projeto
docs/                            — Análise arquitetural, specs
.github/workflows/               — CI (ruff + pytest) + CD (Databricks sync)
```

## Zero interdependência entre Observer Framework e Pipeline

`observer-framework/` e `pipelines/pipeline-seguradora-whatsapp/` = **dois projetos Python independentes**:

- Pipeline **não importa nada** do framework (nenhum `from observer import ...`)
- Framework **não importa nada** do pipeline
- Único ponto de contato = workflow YAML: `deploy/create_workflow.py` adiciona task `observer_trigger` referenciando notebook `observer-framework/notebooks/trigger_sentinel` via path absoluto no Databricks Repo
- No cluster, notebooks do observer-framework adicionam `/Workspace{repo_root}/observer-framework` ao `sys.path` para importar `observer`. Notebooks do pipeline adicionam `/Workspace{repo_root}/pipelines/pipeline-seguradora-whatsapp` ao `sys.path` para importar `pipeline_lib`
- **Nunca** `from observer import ...` em código do pipeline. **Nunca** lógica específica de seguro/WhatsApp no observer-framework

Permite extrair `observer-framework/` como repo Git standalone no futuro (repo privado `RodrigoSiliunas/observer` já existe como placeholder).

## Pipeline seguradora WhatsApp (pipelines/pipeline-seguradora-whatsapp/)

Pipeline Medallion autônomo: Bronze → Silver → Gold sobre conversas WhatsApp de seguro auto (~153k mensagens).

- **Plataforma**: Databricks Trial (AWS), Unity Catalog, Delta Lake
- **Engine**: PySpark em cluster dedicado (m5d.large) — NÃO serverless
- **Workspace**: Via env var `DATABRICKS_HOST`
- **Cluster ID**: Via env var ou deploy script
- **Testes**: 91 testes (pytest), ruff lint
- **Deploy**: Scripts em `pipelines/pipeline-seguradora-whatsapp/deploy/` usando `databricks-sdk`

### Arquitetura ETL

Pipeline ETL **puro** — zero lógica de agente/AI nos notebooks de dados.
Cada camada faz **overwrite idempotente** — Delta Lake garante atomicidade, sem rollback.
Observer Agent = **framework genérico separado** que funciona com qualquer workflow.

```
S3 (Parquet) → [pre_check] → [Bronze] → [Silver x3] → [Gold x12] → [Validation] → [observer_trigger*]
                                                                                          │
                                                                                     *run_if: AT_LEAST_ONE_FAILED
                                                                                          │
                                                                                          ▼
                                                                                    [Observer Agent]
                                                                                    Claude API → GitHub PR
```

### Workflows Databricks

| Job | ID | Tasks | Schedule |
|-----|----|-------|----------|
| ETL Pipeline | (via deploy script) | 8 tasks (7 ETL + 1 sentinel) | Diário 6 AM SP |
| Observer Agent | (via deploy script) | 1 task (on-demand) | Sem schedule |

### Comunicação entre Tasks

Via `dbutils.jobs.taskValues.set/get`. Widgets compartilhados: `catalog`, `scope`, `chaos_mode`, `bronze_prefix`.

### Delta Tables (overwrite idempotente, sem rollback)

- **Catalog**: `medallion` (schemas: bronze, silver, gold)
- Cada notebook faz `overwrite` atômico via Delta Lake
- **Sem rollback Delta** — overwrite idempotente, rodar de novo resolve falha parcial
- `observer_trigger` dispara `workflow_observer_agent` em falha real no ETL
- Observer analisa código, propõe correção, abre PR no GitHub — rollback desnecessário

### S3Lake

Client S3 in-memory (`pipelines/pipeline-seguradora-whatsapp/pipeline_lib/storage/s3_client.py`):
- `dbutils.secrets` para credenciais AWS (multi-tenant ready)
- Leitura: S3 → BytesIO → pandas → Spark DataFrame
- Escrita particionada em chunks de 50k linhas (evita OOM no driver)
- NÃO usa DBFS (desabilitado em serverless)

## Observer Framework (observer-framework/)

Framework genérico de observabilidade para qualquer workflow Databricks. Pacote Python `observer`, 113 testes, docs completas em `observer-framework/docs/`. Detalhes técnicos em `observer-framework/README.md` e `observer-framework/docs/ARCHITECTURE.md`.

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
- Retry com exponential backoff (`@with_retry`) em todas chamadas externas

### WorkflowObserver

- `find_recent_failures()` — busca runs com falha via Jobs API
- `build_failure_from_run()` — extrai detalhes (triggered mode)
- `collect_notebook_code()` — lê código via Workspace API (`w.workspace.export`)
- `collect_schema_info()` — lê schema via Unity Catalog API (auto-discover schemas)
- `build_context()` — monta contexto completo para LLM

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
- S3 buckets: `namastex-medallion-datalake` (dados), `namastex-databricks-root` (Databricks)

## CI/CD

- **CI** (`.github/workflows/ci.yml`): roda ruff + pytest em dois jobs separados — `observer-framework` e `pipeline-seguradora-whatsapp`. Job extra `validate-agent-pr` para branches `fix/*` e `feat/*` rodando ambos.
- **CD** (`.github/workflows/cd.yml`): sincroniza Databricks Repo com `main` automaticamente. Paths monitorados: `observer-framework/**` e `pipelines/**`. Repo Databricks espelha repo inteiro, observer-framework e pipelines atualizados atomicamente.
- **Observer Feedback** (`.github/workflows/observer-feedback.yml`): GitHub Action chamada quando PRs `fix/agent-auto-*` mergeados/fechados — executa `observer-framework/scripts/update_pr_feedback.py`.
- **Fluxo**: Observer cria PR para `dev` → CI valida → humano revisa → merge → dev → PR para main → CD deploya.

## Chaos Testing

Injeção controlada de falhas para testar agente AI end-to-end:

```bash
python pipelines/pipeline-seguradora-whatsapp/deploy/trigger_chaos.py bronze_schema|silver_null|gold_divide_zero|validation_strict
```

Widget `chaos_mode` propagado via task values. Cada notebook ETL tem bloco condicional que injeta falha controlada.

## Convenções

- **Commits**: Conventional Commits em pt-BR (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`)
- **Lint Python**: ruff (line-length=100, py311). Notebooks excluídos do lint.
- **Lint JS/TS**: ESLint flat config + Prettier (double quotes, 2 spaces, 100 chars)
- **Testes Python**: pytest. TDD moderado (obrigatório para `observer/` e `pipeline_lib/`, flexível para notebooks)
- **Testes JS**: Vitest + Vue Test Utils
- **Branch strategy**: PRs do agente AI para `dev` (fix/agent-auto-*, feat/*)
- **Dados sensíveis**: Mascaramento na Silver, HMAC obrigatório sem fallback, redaction do message_body
- **Pacote**: `pipeline_lib` (NÃO `lib` — conflita com stdlib Python no Windows)
- **Schema evolution**: Colunas novas aceitas via Delta `mergeSchema`, nunca rejeitadas
- **Deploy scripts**: Sempre parametrizados via env vars, nunca hardcoded

### Padrão de Notebooks Databricks

1. **Header markdown** primeira célula (`# MAGIC %md` com título, descrição, camada, output, data)
2. **DBTITLE** em TODA célula de código (`# DBTITLE 1,Nome`), NÃO em células %md separadas
3. **Imports** na primeira célula de código: `from...import` primeiro (alfabético), depois `import` (alfabético)
4. **SEM inline imports** — tudo no topo do notebook
5. **Comentários** frequentes em PT-BR com acentuação correta
6. **`dbutils.notebook.exit()`** NUNCA dentro de try/except (exit lança exceção especial capturada pelo except)
7. Separador entre células: `# COMMAND ----------`

### Secrets (Databricks Scope: medallion-pipeline)

| Key | Descrição |
|-----|-----------|
| `aws-access-key-id` | IAM access key |
| `aws-secret-access-key` | IAM secret key |
| `aws-region` | `us-east-2` |
| `s3-bucket` | `namastex-medallion-datalake` |
| `anthropic-api-key` | Claude API key |
| `github-token` | GitHub PAT |
| `masking-secret` | Chave HMAC para PII |

## Erros Conhecidos e Soluções

| Erro | Solução |
|------|---------|
| `CONFIG_NOT_AVAILABLE` (serverless) | Usar `dbutils.widgets.get()` ao invés de `spark.conf.get()` |
| `CANNOT_RESOLVE_DATAFRAME_COLUMN` | Usar `F.col("coluna")` ao invés de `df["col"]` |
| `DBFS_DISABLED` | Usar BytesIO in-memory (S3Lake) |
| `ArrayType(NullType())` | Schema explícito com StructType |
| Lambda/UDF em `F.transform` (serverless) | `collect()` → pandas → `apply()` |
| `dbutils.notebook.exit()` em try/except | Mover exit para FORA do try/except |
| Repo path `[:5]` vs `[:4]` | Sempre `[:4]` para repo root |
| OOM em write S3 | S3Lake.write_parquet com partitioned write (50k chunks) |
| Streaming obrigatório (Claude Opus) | Usar `client.messages.stream()` |

## Roadmap — Melhorias Aprovadas

### Observer Agent (8 melhorias, ordem de prioridade)

1. **Trigger automático** — Webhook/task final do Databricks dispara Observer na hora ao invés de polling
2. **Observabilidade** — Tabela `observer.diagnostics` com timestamp, provider, modelo, tokens, confiança, PR URL, tempo de resolução + Dashboard SQL
3. **Deduplicação de diagnósticos** — Cache via tabela Delta (hash do error message), evita PRs duplicados e gasto de tokens
4. **Modo dry-run** — Widget `dry_run=true` diagnostica mas NÃO cria PR, só loga
5. **Configuração como código** — YAML/JSON no repo ao invés de widgets (llm_provider, model, git_provider, max_retries, etc.)
6. **Validação pré-PR** — Rodar ruff + pytest no fix ANTES de criar PR, rejeitar fixes inválidos
7. **Multi-file fixes** — LLM pode propor changes em N arquivos (GitProvider aceita lista de file_path/code)
8. **Feedback loop** — Webhook GitHub notifica quando PR mergeado/fechado, atualiza tabela de diagnósticos

### Confiança do Agente AI

Nível de confiança atual = auto-avaliado pelo LLM (heurística).
Melhoria futura: pipeline de validação pós-diagnóstico que roda testes unitários no fix antes de atribuir score numérico.

### Visão de Produto — One-Click Deploy

Projeto evoluiu de teste técnico para produto real. Visão:
- **Marketplace** de pipeline templates (WhatsApp seguros, SAP, CRM, ERP...)
- **Deploy one-click**: conecta AWS + Databricks, escolhe template, configura envs, clica "Deploy"
- **Terraform programático** + **Databricks SDK** criam toda infra automaticamente
- **Princípios**: atomicidade (saga pattern), idempotência (IF NOT EXISTS), versionamento de templates, multi-empresa
- **Execução**: Celery async + SSE para progresso tempo real no frontend
- **Tagging**: AWS + Databricks tags para governança e custos por pipeline/empresa/time

## GitHub

- **Repo**: `RodrigoSiliunas/agentic-workflow-medallion-pipeline`
- **Admin email**: Via deploy