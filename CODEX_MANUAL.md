# Manual de Desenvolvimento - Codex

> Este manual documenta todos os padroes, decisoes arquiteturais e fluxos de trabalho do projeto
> **Agentic Workflow Medallion Pipeline**. Use-o como referencia completa para continuar o
> desenvolvimento com o mesmo nivel de contexto da sessao original.
>
> **Criado em:** 2026-04-09 | **Autor do projeto:** Rodrigo Siliunas

---

## Indice

1. [Visao Geral do Projeto](#1-visao-geral-do-projeto)
2. [Estrutura do Monorepo](#2-estrutura-do-monorepo)
3. [Arquitetura Medallion Pipeline](#3-arquitetura-medallion-pipeline)
4. [Observer Agent Framework](#4-observer-agent-framework)
5. [Notebooks Databricks - Padroes](#5-notebooks-databricks---padroes)
6. [pipeline_lib - Biblioteca Compartilhada](#6-pipeline_lib---biblioteca-compartilhada)
7. [Deploy e Infraestrutura](#7-deploy-e-infraestrutura)
8. [CI/CD](#8-cicd)
9. [Chaos Testing](#9-chaos-testing)
10. [Plataforma Conversacional](#10-plataforma-conversacional)
11. [Terraform / AWS](#11-terraform--aws)
12. [Convencoes de Codigo](#12-convencoes-de-codigo)
13. [Ambiente e Credenciais](#13-ambiente-e-credenciais)
14. [Erros Comuns e Solucoes](#14-erros-comuns-e-solucoes)
15. [Roadmap de Melhorias](#15-roadmap-de-melhorias)
16. [Comandos Frequentes](#16-comandos-frequentes)

---

## 1. Visao Geral do Projeto

**Nome:** Agentic Workflow Medallion Pipeline
**Objetivo:** Pipeline de dados sobre conversas WhatsApp de seguro auto (~153k mensagens).
Transforma dados brutos em analytics acionaveis com um agente autonomo de IA que monitora,
diagnostica e corrige falhas automaticamente via PRs no GitHub.

### Tres partes:

| Parte | Descricao | Status |
|-------|-----------|--------|
| **Pipeline Medallion** | ETL Bronze > Silver > Gold + Observer Agent | Implementado |
| **Plataforma Conversacional** | SaaS multi-tenant (Nuxt 4 + FastAPI) | Em desenvolvimento |
| **Infra as Code** | Terraform AWS (S3, IAM, Security Groups) | Criado, pendente execucao |

### Principio fundamental

O pipeline ETL eh **puro** — zero logica de agente/AI nos notebooks de dados.
O Observer Agent eh um **framework generico separado** que funciona com qualquer workflow Databricks.

---

## 2. Estrutura do Monorepo

```
/
├── pipeline/                    # Pipeline Medallion (Databricks + AWS)
│   ├── notebooks/               # Databricks notebooks (.py source format)
│   │   ├── agent_pre.py         # Task 0: pre-flight checks, fingerprint S3
│   │   ├── bronze/
│   │   │   └── ingest.py        # Task 1: S3 parquet → Delta bronze
│   │   ├── silver/
│   │   │   ├── dedup_clean.py   # Task 2: dedup + normalização
│   │   │   ├── entities_mask.py # Task 3: extração + mascaramento PII
│   │   │   └── enrichment.py    # Task 4: métricas conversacionais
│   │   ├── gold/
│   │   │   ├── analytics.py     # Task 5: orquestrador (12 notebooks paralelos)
│   │   │   ├── funnel.py        # Funil de vendas
│   │   │   ├── sentiment.py     # Análise de sentimento
│   │   │   ├── lead_scoring.py  # Scoring de leads
│   │   │   └── ...              # +9 notebooks analíticos
│   │   ├── validation/
│   │   │   └── checks.py        # Task 6: quality gates
│   │   ├── agent_post.py        # Task 7: rollback Delta + handoff para o sentinel
│   │   └── observer/
│   │       ├── collect_and_fix.py  # Notebook do Observer Agent
│   │       └── trigger_sentinel.py # Task final: dispara o Observer automaticamente
│   │
│   ├── pipeline_lib/            # Biblioteca Python compartilhada
│   │   ├── agent/
│   │   │   ├── observer/        # Framework Observer Agent
│   │   │   │   ├── workflow_observer.py
│   │   │   │   └── providers/   # Factory pattern (LLM + Git)
│   │   │   │       ├── __init__.py        # Registry + factory
│   │   │   │       ├── base.py            # ABCs + dataclasses
│   │   │   │       ├── anthropic_provider.py
│   │   │   │       ├── openai_provider.py
│   │   │   │       └── github_provider.py
│   │   │   ├── llm_diagnostics.py  # (legacy, substituido pelo observer)
│   │   │   └── github_pr.py        # (legacy, substituido pelo observer)
│   │   ├── storage/
│   │   │   └── s3_client.py     # S3Lake: leitura/escrita S3 via boto3 in-memory
│   │   ├── schema/
│   │   │   ├── contracts.py     # Colunas obrigatorias + constraints
│   │   │   └── validator.py     # Validador de schema
│   │   ├── extractors/          # Extratores de entidades (CPF, phone, email, etc)
│   │   └── masking/             # Mascaramento PII (HMAC, redaction, format-preserving)
│   │
│   ├── deploy/                  # Scripts de deploy/gestao Databricks
│   │   ├── create_workflow.py          # Cria job ETL (6 tasks)
│   │   ├── create_observer_workflow.py # Cria job Observer (1 task)
│   │   ├── trigger_run.py              # Dispara execucao do pipeline
│   │   ├── trigger_chaos.py            # Dispara chaos testing
│   │   ├── upload_data.py              # Upload parquet para S3
│   │   ├── setup_catalog.py            # Cria catalog + schemas no Unity Catalog
│   │   └── dashboard_queries.sql       # Queries para dashboard SQL
│   │
│   └── tests/                   # Testes pytest (89 testes)
│
├── platform/
│   ├── frontend/                # Nuxt 4.4.2 + Vue 3 + TypeScript
│   └── backend/                 # FastAPI async + PostgreSQL
│
├── infra/
│   └── aws/
│       ├── 01-foundation/       # IAM, Security Groups, Secrets, S3 root
│       └── 02-datalake/         # S3 medallion bucket + lifecycle
│
├── conductor/                   # Tracks e workflow do projeto
├── docs/                        # Analise arquitetural, specs
├── .github/workflows/           # CI (ruff + pytest) + CD (Databricks sync)
├── CLAUDE.md                    # Instrucoes para AI assistants
└── .env.example                 # Template de variaveis de ambiente
```

> **IMPORTANTE:** O pacote se chama `pipeline_lib` (nao `lib`) porque `lib` conflita com a
> stdlib do Python no Windows. Todos os imports usam `from pipeline_lib.xxx import yyy`.

---

## 3. Arquitetura Medallion Pipeline

### Fluxo de Dados

```
S3 (Parquet bruto)
    │
    ▼
[agent_pre] ─── Verifica fingerprint S3, captura versoes Delta para rollback
    │
    ▼
[Bronze] ─────── S3Lake.read_parquet() → schema validation → Delta overwrite
    │
    ▼
[Silver] ─────── Dedup → Entity extraction + PII masking → Enrichment (metricas)
    │
    ▼
[Gold] ────────── 12 notebooks analiticos em 3 fases paralelas (ThreadPoolExecutor)
    │
    ▼
[Validation] ──── Row counts, null rates, consistency checks
    │
    ▼
[agent_post] ──── Coleta resultados → rollback se falhou → handoff para sentinel
    │
    ▼
[observer_trigger] ──── dispara Observer Agent automaticamente
    │
    ▼
[Observer] ─────── (Job separado) Claude API diagnostics → GitHub PR
```

### Workflow Databricks (Job ID: 777105089901314)

9 tasks sequenciais no job ETL principal:

| Task | Notebook | Depends On |
|------|----------|------------|
| `agent_pre` | `agent_pre.py` | — |
| `bronze_ingestion` | `bronze/ingest.py` | agent_pre |
| `silver_dedup` | `silver/dedup_clean.py` | bronze_ingestion |
| `silver_entities` | `silver/entities_mask.py` | silver_dedup |
| `silver_enrichment` | `silver/enrichment.py` | silver_entities |
| `gold_analytics` | `gold/analytics.py` | silver_enrichment |
| `quality_validation` | `validation/checks.py` | gold_analytics |
| `agent_post` | `agent_post.py` | quality_validation (run_if: ALL_DONE) |
| `observer_trigger` | `observer/trigger_sentinel.py` | agent_post + tasks upstream (run_if: AT_LEAST_ONE_FAILED) |

**Shared Parameters (widgets):**
- `catalog` = "medallion"
- `scope` = "medallion-pipeline"
- `chaos_mode` = "off"
- `bronze_prefix` = "bronze/"

### Observer Workflow (Job ID: 848172838529828)

1 task, sem schedule, disparado on-demand:

| Task | Notebook | Params |
|------|----------|--------|
| `observe_and_fix` | `observer/collect_and_fix.py` | source_run_id, catalog, scope, llm_provider, git_provider |

`max_concurrent_runs = 3` — pode rodar multiplas instancias simultaneamente.

### Comunicacao entre Tasks

Via `dbutils.jobs.taskValues`:
```python
# Setar (no notebook produtor)
dbutils.jobs.taskValues.set(key="chaos_mode", value="off")

# Ler (no notebook consumidor)
chaos_mode = dbutils.jobs.taskValues.get(
    taskKey="agent_pre", key="chaos_mode", default="off"
)
```

### Delta Tables

**Catalog:** `medallion`

| Schema | Tabela | Descricao |
|--------|--------|-----------|
| bronze | conversations | Dados brutos do S3 |
| silver | messages_clean | Mensagens deduplicadas |
| silver | leads_profile | Perfis de leads |
| silver | conversations_enriched | Metricas conversacionais |
| gold | funil_vendas | Funil de conversao |
| gold | agent_performance | Performance dos agentes |
| gold | sentiment | Analise de sentimento |
| gold | lead_scoring | Scoring de leads |
| gold | email_providers | Providers de email |
| gold | temporal_analysis | Analise temporal |
| gold | competitor_intel | Inteligencia competitiva |
| gold | campaign_roi | ROI de campanhas |
| gold | personas | Segmentacao de personas |
| gold | churn_reengagement | Churn e reengajamento |
| gold | negotiation_complexity | Complexidade de negociacao |
| gold | first_contact_resolution | Resolucao no primeiro contato |

### Atomicidade e Rollback

- Cada notebook faz `df.write.mode("overwrite")` — atomico via Delta Lake
- `agent_pre` captura `deltaTable.history(1)` de TODAS as tabelas antes da execucao
- Se pipeline falha, `agent_post` faz `RESTORE TABLE ... TO VERSION AS OF {v}` para cada tabela
- Depois do rollback, `observer_trigger` dispara o Observer com `source_run_id`, `source_job_id`, `source_job_name` e `failed_tasks`
- Mapeamento task → tabela definido em `agent_post.py`:
  ```python
  ROLLBACK_MAP = {
      "bronze_ingestion": ["bronze.conversations"],
      "silver_dedup": ["silver.messages_clean", "silver.leads_profile"],
      ...
  }
  ```

### Gold Analytics - Paralelismo

`gold/analytics.py` usa `ThreadPoolExecutor` com 3 fases:

```python
phases = [
    {"name": "Core", "notebooks": [funnel, agent_performance, sentiment, email_providers]},
    {"name": "Scoring + Analytics", "notebooks": [lead_scoring, temporal_analysis, competitor_intel]},
    {"name": "Avancado", "notebooks": [campaign_roi, segmentation, churn, negotiation, fcr]},
]
# Fases rodam em SEQUENCIA (dependencias), notebooks dentro de cada fase em PARALELO
```

---

## 4. Observer Agent Framework

### Arquitetura

O Observer eh um **framework generico** que funciona com **qualquer workflow Databricks**.
Nao conhece nada sobre o pipeline Medallion especificamente.

```
WorkflowObserver (coleta contexto)
    │
    ├── find_recent_failures()     # Busca runs com falha
    ├── build_failure_from_run()   # Extrai detalhes da falha
    ├── collect_notebook_code()    # Le codigo via Workspace API (base64)
    ├── collect_schema_info()      # Le schema via Unity Catalog API
    └── build_context()            # Monta contexto completo para LLM
         │
         ▼
    LLMProvider.diagnose()         # Factory: anthropic, openai, ollama...
         │
         ▼
    GitProvider.create_fix_pr()    # Factory: github, gitlab, bitbucket...
```

### Factory Pattern (Providers)

**Arquivo:** `pipeline_lib/agent/observer/providers/__init__.py`

```python
from pipeline_lib.agent.observer.providers import (
    create_llm_provider,    # Factory para LLM
    create_git_provider,    # Factory para Git
    DiagnosisRequest,       # Input do diagnóstico
    DiagnosisResult,        # Output do diagnóstico
    PRResult,               # Output do PR
)

# Criar provider
llm = create_llm_provider("anthropic", api_key="sk-...", model="claude-opus-4-20250514")
git = create_git_provider("github", token="ghp_...", repo="owner/repo")

# Usar
result = llm.diagnose(DiagnosisRequest(...))
pr = git.create_fix_pr(result, failed_task="bronze_ingestion")
```

**Registry via decorators:**
```python
@register_llm_provider("anthropic")
class AnthropicProvider(LLMProvider): ...

@register_llm_provider("openai")
class OpenAIProvider(LLMProvider): ...

@register_git_provider("github")
class GitHubProvider(GitProvider): ...
```

### LLM Providers Implementados

| Provider | Modelo Default | Streaming | Retry |
|----------|---------------|-----------|-------|
| `anthropic` | claude-opus-4-20250514 | Sim (obrigatorio para Opus) | 3x exponential backoff |
| `openai` | gpt-4o | Nao | 3x exponential backoff |

**Ambos usam o mesmo SYSTEM_PROMPT** (engenheiro de dados senior, PySpark/Delta/Databricks).
**Ambos retornam JSON estruturado** com: diagnosis, root_cause, fix_description, fixed_code, file_to_fix, confidence.

### Git Providers Implementados

| Provider | Branch Pattern | PR Target |
|----------|---------------|-----------|
| `github` | `fix/agent-auto-{task}-{timestamp}` | `dev` branch |

PR body inclui: emoji de confianca (verde/amarelo/vermelho), diagnostico, causa raiz, descricao do fix, provider/model usado.

### Retry/Backoff

Decorator `@with_retry` em `base.py`:
```python
@with_retry(max_retries=3, base_delay=2.0)
def diagnose(self, request): ...
```
- Retenta em erros transientes (rede, rate limit, timeout)
- NAO retenta em erros de logica (ValueError, KeyError, TypeError)
- Exponential backoff: 2s, 4s, 8s

### DataClasses

```python
@dataclass
class DiagnosisRequest:
    error_message: str
    stack_trace: str
    failed_task: str
    notebook_code: str      # Codigo fonte lido via Workspace API
    schema_info: str        # Schema das tabelas do Unity Catalog
    pipeline_state: dict    # job_name, job_id, run_id, failed_tasks, all_errors

@dataclass
class DiagnosisResult:
    diagnosis: str
    root_cause: str
    fix_description: str
    fixed_code: str | None
    file_to_fix: str | None
    confidence: float       # 0.0 a 1.0
    requires_human_review: bool
    additional_notes: str
    provider: str           # "anthropic", "openai"
    model: str              # "claude-opus-4-20250514", "gpt-4o"
    input_tokens: int
    output_tokens: int

@dataclass
class PRResult:
    pr_url: str
    pr_number: int
    branch_name: str
```

---

## 5. Notebooks Databricks - Padroes

### Formato

Notebooks sao arquivos `.py` com formato Databricks Source:
- Separador entre celulas: `# COMMAND ----------`
- Primeira linha: `# Databricks notebook source`
- Titulos nas celulas: `# DBTITLE 1,Nome do Titulo`
- Magics: `# MAGIC %md`, `# MAGIC %sql`, etc.

### Template de Notebook

```python
# Databricks notebook source
# MAGIC %md
# MAGIC # Camada: Nome do Notebook
# MAGIC Descricao do que faz.
# MAGIC
# MAGIC **Camada:** Bronze/Silver/Gold | **Dependencia:** tabela X
# MAGIC **Output:** tabela Y
# MAGIC
# MAGIC _Ultima atualizacao: 2026-04-09_

# COMMAND ----------

# DBTITLE 1,Imports e Setup
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType

import logging
import time

logger = logging.getLogger("camada.nome")
start_time = time.time()

# COMMAND ----------

# DBTITLE 1,Parametros
dbutils.widgets.text("catalog", "medallion", "Catalog Name")
dbutils.widgets.text("scope", "medallion-pipeline", "Secret Scope")

CATALOG = dbutils.widgets.get("catalog")
SCOPE = dbutils.widgets.get("scope")

# COMMAND ----------

# DBTITLE 1,Logica Principal
# ... codigo aqui ...

# COMMAND ----------

# DBTITLE 1,Saida
dbutils.notebook.exit("SUCCESS: descricao do resultado")
```

### Regras OBRIGATORIAS

1. **DBTITLE** em TODA celula de codigo (nao em celulas %md separadas)
2. **Header markdown** como primeira celula (titulo, descricao, camada, output, data)
3. **Imports** todos na primeira celula de codigo, ordenados:
   - `from ... import ...` primeiro (alfabetico)
   - `import ...` depois (alfabetico)
4. **Comentarios** frequentes em PT-BR com acentuacao correta
5. **SEM inline imports** — tudo no topo
6. **Sem serverless** — pipeline roda em cluster dedicado (m5d.large)
7. **dbutils.notebook.exit()** NUNCA dentro de try/except (exit lanca excecao especial)
8. **Schema evolution**: colunas novas sao aceitas via Delta `mergeSchema`, nunca rejeitadas

### Comunicacao via Task Values

```python
# Setar valor (produtor)
dbutils.jobs.taskValues.set(key="status", value="SUCCESS")

# Ler valor (consumidor)
status = dbutils.jobs.taskValues.get(
    taskKey="nome_da_task", key="status", default="UNKNOWN"
)
```

### Auto-detect do Repo Path

Todo notebook que chama sub-notebooks usa:
```python
_nb_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
_repo_root = "/".join(_nb_path.split("/")[:4])
NOTEBOOK_BASE = f"{_repo_root}/pipeline/notebooks"
```

### Chaos Mode Pattern

Cada notebook ETL pode receber chaos mode para teste:
```python
# Lê chaos mode da task anterior
chaos_mode = ""
try:
    chaos_mode = dbutils.jobs.taskValues.get(
        taskKey="agent_pre", key="chaos_mode", default="off"
    )
except Exception:
    chaos_mode = "off"

if chaos_mode == "bronze_schema":
    logger.warning("CHAOS MODE: Injetando bug de schema")
    # ... injeta falha controlada ...
```

---

## 6. pipeline_lib - Biblioteca Compartilhada

### S3Lake (`storage/s3_client.py`)

Client S3 que funciona tanto em serverless quanto em cluster:

```python
from pipeline_lib.storage import S3Lake

lake = S3Lake(dbutils, spark, scope="medallion-pipeline")

# Leitura: S3 → BytesIO → pandas → Spark DataFrame
df = lake.read_parquet("bronze/")

# Escrita: Spark DF → partições pandas (50k rows) → BytesIO → S3
lake.write_parquet(df, "silver/clean/")
```

**Detalhes importantes:**
- Usa `dbutils.secrets` para credenciais AWS (multi-tenant ready)
- Leitura via BytesIO (nao DBFS — DBFS desabilitado em serverless)
- Escrita particionada em chunks de 50k linhas para evitar OOM no driver
- Paginacao automatica para `list_objects_v2` (buckets grandes)

### Schema Contracts (`schema/contracts.py`)

```python
REQUIRED_COLUMNS = {
    "message_id", "conversation_id", "timestamp", "direction",
    "sender_phone", "sender_name", "message_type", "message_body",
    "status", "channel", "campaign_id", "agent_id",
    "conversation_outcome", "metadata",
}

VALUE_CONSTRAINTS = {
    "conversation_id": r"^conv_[0-9a-f]{8}$",
    "direction": {"inbound", "outbound"},
    "message_type": {"text", "audio", "image", "document", "sticker", "contact", "video", "location"},
    "status": {"sent", "delivered", "read", "failed"},
    "channel": {"whatsapp"},
}
```

### Extractors (`extractors/`)

Extratores de entidades:
- `cpf.py` — CPF brasileiro (regex + validacao digitos)
- `phone.py` — Telefones BR
- `email.py` — Enderecos de email
- `cep.py` — CEP
- `plate.py` — Placas de veiculo
- `vehicle.py` — Marcas/modelos
- `price.py` — Valores monetarios
- `competitor.py` — Nomes de concorrentes

### Masking (`masking/`)

Mascaramento PII:
- `hash_based.py` — HMAC-SHA256 (obrigatorio, sem fallback)
- `redaction.py` — Redacao de texto sensivel
- `format_preserving.py` — Mascaramento preservando formato

> **REGRA:** HMAC eh obrigatorio. Nunca usar hash simples sem chave secreta.
> A chave vem de `MASKING_SECRET` no .env / Databricks Secrets.

---

## 7. Deploy e Infraestrutura

### Scripts de Deploy (`deploy/`)

Todos os scripts usam `databricks-sdk` e variaveis de ambiente:

```bash
# Variaveis obrigatorias
export DATABRICKS_HOST="https://dbc-1bad7a6a-cc31.cloud.databricks.com"
export DATABRICKS_TOKEN="dapi..."

# Criar workflow ETL
python pipeline/deploy/create_workflow.py

# Criar workflow Observer
python pipeline/deploy/create_observer_workflow.py

# Setup Unity Catalog (catalog + schemas)
python pipeline/deploy/setup_catalog.py

# Upload dados para S3
python pipeline/deploy/upload_data.py

# Disparar execucao
python pipeline/deploy/trigger_run.py

# Disparar chaos test
python pipeline/deploy/trigger_chaos.py bronze_schema
```

### Parametrizacao por Empresa

Scripts NUNCA tem valores hardcoded. Tudo via variaveis de ambiente:

```python
DATABRICKS_HOST = os.environ["DATABRICKS_HOST"]
DATABRICKS_TOKEN = os.environ["DATABRICKS_TOKEN"]
PIPELINE_CLUSTER_ID = os.environ.get("PIPELINE_CLUSTER_ID", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "RodrigoSiliunas/agentic-workflow-medallion-pipeline")
```

### create_workflow.py - Detalhes

- Cria job ETL com 6 tasks sequenciais
- Usa `existing_cluster_id` (nao serverless, nao job cluster)
- Schedule: diario as 6 AM Sao Paulo
- Tags: `project=medallion-pipeline`, `env=production`
- Timeout: 3600 segundos
- Email notifications para `administrator@idlehub.com.br`
- `chaos_mode` nos shared parameters (default: "off")
- Idempotente: se job existe, atualiza (reset + update)

### create_observer_workflow.py - Detalhes

- Job separado, sem schedule
- Disparado via SDK quando pipeline falha
- `max_concurrent_runs = 3`
- Timeout: 900 segundos
- Parameters: `source_run_id`, `source_job_id`, `source_job_name`, `failed_tasks`, `catalog`, `scope`, `llm_provider`, `git_provider`

### Databricks Workspace

- **Workspace:** `data-capture-engine-prd`
- **URL:** `https://dbc-1bad7a6a-cc31.cloud.databricks.com`
- **Cluster:** `0409-064526-q0k9e0pd` (m5d.large, Databricks trial)
- **Repo path:** `/Repos/administrator@idlehub.com.br/agentic-workflow-medallion-pipeline`
- O Databricks Repo sincroniza com GitHub via CD pipeline

### Databricks Secrets (Scope: `medallion-pipeline`)

| Key | Descricao |
|-----|-----------|
| `aws-access-key-id` | IAM access key |
| `aws-secret-access-key` | IAM secret key |
| `aws-region` | `us-east-1` |
| `s3-bucket` | `namastex-medallion-datalake` |
| `anthropic-api-key` | Claude API key |
| `github-token` | GitHub PAT |
| `masking-secret` | Chave HMAC para PII |

---

## 8. CI/CD

### CI (`.github/workflows/ci.yml`)

Roda em push para `main`/`dev` e em PRs:

```yaml
jobs:
  pipeline-lint-test:
    - ruff check pipeline/pipeline_lib/   # Lint
    - pytest pipeline/tests/ -v           # 89 testes

  validate-agent-pr:
    # Roda apenas em branches fix/* e feat/* (PRs do agente)
    - ruff check pipeline/pipeline_lib/
    - pytest pipeline/tests/ -v
```

### CD (`.github/workflows/cd.yml`)

Roda em push para `main`:

1. Sincroniza Databricks Repo com `main` branch
2. Verifica que repo esta synchronized
3. Verifica que job existe
4. Posta summary no GitHub Actions

```yaml
env:
  DATABRICKS_HOST: ${{ secrets.DATABRICKS_HOST }}
  DATABRICKS_TOKEN: ${{ secrets.DATABRICKS_TOKEN }}
  DATABRICKS_REPO_PATH: /Repos/administrator@idlehub.com.br/agentic-workflow-medallion-pipeline
```

### Fluxo GitHub

```
Branches:
  main  ─── branch de producao (CD deploya automaticamente)
  dev   ─── branch de desenvolvimento (PRs do agente AI vao para ca)
  fix/* ─── branches criadas pelo Observer Agent
  feat/*─── branches de feature

Fluxo normal:
  dev → PR para main → merge → CD sync → Databricks atualizado

Fluxo do agente:
  Observer detecta falha → cria branch fix/agent-auto-xxx → PR para dev
  → CI valida (ruff + pytest) → humano revisa → merge para dev
  → dev → PR para main (manual ou automatico)
```

---

## 9. Chaos Testing

### Objetivo

Injetar bugs controlados para testar que o agente AI funciona end-to-end:
deteccao → rollback Delta → Claude API diagnostics → GitHub PR para dev.

### 4 Cenarios

| Modo | Injecao | Efeito |
|------|---------|--------|
| `bronze_schema` | Coluna `_chaos_invalid_col` com tipo incompativel | Schema validation falha |
| `silver_null` | NULLs em `conversation_id` | Dedup/groupBy falha |
| `gold_divide_zero` | `F.lit(1) / F.lit(0)` | ArithmeticException |
| `validation_strict` | Threshold impossivel | Quality check FAIL |

### Como Usar

```bash
# Via CLI
python pipeline/deploy/trigger_chaos.py bronze_schema

# Via Databricks UI
# Job Settings → Edit → Base Parameters → chaos_mode = "bronze_schema" → Run Now
```

### Fluxo Esperado

```
1. trigger_chaos.py dispara pipeline com chaos_mode=X
2. agent_pre → SUCCESS (propaga chaos_mode via task value)
3. Notebook alvo → FAILED (bug injetado)
4. Notebooks downstream → UPSTREAM_FAILED
5. agent_post:
   a. Detecta falha
   b. Rollback Delta (restaura versao anterior)
6. observer_trigger:
   a. Recebe o parent run do workflow
   b. Identifica as tasks que falharam de verdade
   c. Trigger Observer Agent
7. Observer:
   a. Coleta codigo do notebook + erro + schema
   b. Claude Opus analisa e propoe fix
   c. GitHub PR criado em branch fix/agent-auto-*
8. Verificar: PR no GitHub? Diagnostico correto? Fix faz sentido?
```

---

## 10. Plataforma Conversacional

### Frontend (`platform/frontend/`)

| Item | Valor |
|------|-------|
| Framework | Nuxt 4.4.2 + Vue 3 + TypeScript |
| Package Manager | Bun |
| UI Library | @nuxt/ui (Tailwind-based) |
| State | Pinia |
| Composables | @vueuse/nuxt |
| Componentes | Atomic Design (atoms/molecules/organisms/templates) |

### Backend (`platform/backend/`)

| Item | Valor |
|------|-------|
| Framework | FastAPI (async) |
| Auth | JWT + API Key, RBAC (viewer/editor/admin), multi-tenant |
| DB | PostgreSQL (SQLAlchemy 2 async) |
| Cache | Redis |
| Padroes | Service layer, domain exceptions, Pydantic Settings, lifespan hooks |

### Padroes do idlehub

O Rodrigo segue os padroes do idlehub:
- `useApiClient` com token refresh automatico e request queue
- Multi-tenancy com DB isolation (master + tenant DBs)
- AuthContext dataclass para JWT + API Key
- Service layer pattern (async)
- Domain exceptions mapeadas para HTTP status
- Redis rate limiting com fallback in-memory
- SWR caching via useDataCache
- Global middleware para auth

---

## 11. Terraform / AWS

### Estrutura

```
infra/aws/
├── 01-foundation/         # IAM, Security Groups, Secrets Manager
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── iam_users.tf
│   ├── iam_roles.tf       # Self-assuming + external ID
│   ├── iam_policies.tf    # S3, EC2/VPC, STS, root storage, secrets
│   ├── security_groups.tf
│   ├── secrets.tf
│   └── databricks_root.tf # S3 bucket para Databricks root
│
└── 02-datalake/           # S3 Medallion bucket
    ├── main.tf
    ├── variables.tf
    └── outputs.tf
```

### Detalhes Importantes

- Account ID dinamico via `data.aws_caller_identity.current.account_id`
- NAO hardcodar account ID em nenhum lugar
- S3 buckets: `namastex-databricks-root` (Databricks), `namastex-medallion-datalake` (dados)
- Lifecycle rules: Glacier apos 90 dias para bronze
- Databricks workspace criado manualmente (trial) — Terraform gerencia o resto

### Workspace Setup

1. Credential Configuration: IAM role para cross-account access
2. Storage Configuration: S3 bucket para Databricks managed storage
3. Managed VPC com subnets e security groups

---

## 12. Convencoes de Codigo

### Commits

Conventional Commits em **PT-BR**:
```
feat: adiciona analise de sentimento na Gold
fix: corrige dedup ignorando NULLs no conversation_id
refactor: extrai S3Lake para pipeline_lib/storage
docs: atualiza README com arquitetura do Observer
test: adiciona testes para mascaramento HMAC
```

### Python (ruff)

```toml
# ruff config
line-length = 100
target-version = "py311"
# Notebooks excluidos do lint
```

### JS/TS (ESLint + Prettier)

- ESLint flat config
- Prettier: double quotes, 2 spaces, 100 chars

### Branch Strategy

| Branch | Uso |
|--------|-----|
| `main` | Producao (CD auto-deploy) |
| `dev` | Desenvolvimento |
| `fix/agent-auto-*` | Criadas automaticamente pelo Observer |
| `feat/*` | Features manuais |

### Dados Sensiveis

- Mascaramento na Silver com HMAC (obrigatorio, sem fallback)
- message_body eh redacted na Silver
- Nunca commitar .env, credenciais, tokens
- Secrets via Databricks Secret Scope

---

## 13. Ambiente e Credenciais

### Variaveis de Ambiente (.env)

```bash
# AWS
S3_BUCKET=namastex-medallion-datalake
S3_BRONZE_PATH=s3://namastex-medallion-datalake/bronze/

# Databricks
DATABRICKS_HOST=https://dbc-1bad7a6a-cc31.cloud.databricks.com
DATABRICKS_TOKEN=dapi...

# Anthropic (Claude API)
ANTHROPIC_API_KEY=sk-ant-api03-...

# GitHub
GITHUB_TOKEN=ghp_...
GITHUB_REPO=RodrigoSiliunas/agentic-workflow-medallion-pipeline

# Unity Catalog
CATALOG_NAME=medallion
BRONZE_SCHEMA=bronze
SILVER_SCHEMA=silver
GOLD_SCHEMA=gold

# Mascaramento
MASKING_SECRET=your-secret-key-here

# Cluster (opcional, se nao usar serverless)
PIPELINE_CLUSTER_ID=0409-064526-q0k9e0pd
```

### GitHub Secrets (para CI/CD)

| Secret | Uso |
|--------|-----|
| `DATABRICKS_HOST` | CD: sync repo |
| `DATABRICKS_TOKEN` | CD: auth Databricks |
| `DATABRICKS_REPO_PATH` | CD: path do repo no workspace |

### AWS Account

- Account ID: `051457670776`
- Regiao: `us-east-1`
- IAM user: criado via Terraform
- Buckets: `namastex-medallion-datalake`, `namastex-databricks-root`

---

## 14. Erros Comuns e Solucoes

### Databricks

| Erro | Causa | Solucao |
|------|-------|---------|
| `CONFIG_NOT_AVAILABLE` | `spark.conf.get()` em serverless | Usar `dbutils.widgets.get()` |
| `CANNOT_RESOLVE_DATAFRAME_COLUMN` | `spark.table(X)["col"]` ambiguo | Usar `F.col("coluna")` |
| `DBFS_DISABLED` | `/tmp` em serverless | Usar BytesIO in-memory |
| `ArrayType(NullType())` | Arrays vazios | Schema explicito com StructType |
| `PlanMetrics not JSON serializable` | `toPandas()` em serverless | `collect()` + `asDict()` |
| Lambda/UDF em `F.transform` | Serverless bloqueia UDFs | Usar `collect()` → pandas → apply |
| `dbutils.notebook.exit()` dentro de try | Exit lanca excecao capturada | Exit FORA de try/except |
| Repo path `[:5]` vs `[:4]` | Double `/pipeline/pipeline` | Sempre `[:4]` para repo root |

### S3

| Erro | Causa | Solucao |
|------|-------|---------|
| AccessDenied | IAM policy com bucket name errado | Verificar `var.bucket_name` |
| OOM no write | toPandas() em dataset grande | Usar partitioned write (50k chunks) |

### Claude API

| Erro | Causa | Solucao |
|------|-------|---------|
| Streaming required | `max_tokens > X` sem stream | Usar `client.messages.stream()` |
| Key expirada | Token rotacionado | Atualizar em Databricks Secrets |

---

## 15. Roadmap de Melhorias

8 melhorias aprovadas para o Observer Agent (em ordem de prioridade):

| # | Nome | Descricao |
|---|------|-----------|
| 1 | **Trigger automatico** | Webhook/task final do Databricks dispara Observer imediatamente |
| 7 | **Observabilidade** | Tabela `observer.diagnostics` + Dashboard SQL |
| 2 | **Deduplicacao** | Cache de diagnosticos (hash do erro), evita PRs duplicados |
| 9 | **Modo dry-run** | Widget `dry_run=true` — diagnostica mas nao cria PR |
| 8 | **Config como codigo** | YAML/JSON no repo ao inves de widgets |
| 6 | **Validacao pre-PR** | Rodar ruff + pytest antes de criar PR |
| 5 | **Multi-file fixes** | LLM propoe changes em N arquivos |
| 3 | **Feedback loop** | Webhook GitHub notifica quando PR eh mergeado/fechado |

Tracks do Conductor precisam ser criados para cada melhoria.

---

## 16. Comandos Frequentes

### Desenvolvimento Local

```bash
# Lint
ruff check pipeline/pipeline_lib/

# Testes
pytest pipeline/tests/ -v

# Lint + fix
ruff check pipeline/pipeline_lib/ --fix
```

### Deploy

```bash
# Setup completo (primeira vez)
python pipeline/deploy/setup_catalog.py
python pipeline/deploy/upload_data.py
python pipeline/deploy/create_workflow.py
python pipeline/deploy/create_observer_workflow.py

# Execucao
python pipeline/deploy/trigger_run.py

# Chaos testing
python pipeline/deploy/trigger_chaos.py bronze_schema
python pipeline/deploy/trigger_chaos.py silver_null
python pipeline/deploy/trigger_chaos.py gold_divide_zero
python pipeline/deploy/trigger_chaos.py validation_strict
```

### Git

```bash
# Branch de feature
git checkout -b feat/minha-feature dev
# ... trabalhar ...
git push -u origin feat/minha-feature
gh pr create --base dev

# Merge para main (apos PR aprovado)
git checkout main
git merge dev
git push origin main  # Triggers CD
```

### Databricks SDK

```python
from databricks.sdk import WorkspaceClient

w = WorkspaceClient(
    host="https://dbc-1bad7a6a-cc31.cloud.databricks.com",
    token="dapi..."
)

# Listar jobs
for job in w.jobs.list():
    print(job.job_id, job.settings.name)

# Disparar run
run = w.jobs.run_now(job_id=777105089901314)

# Ver run output
output = w.jobs.get_run_output(run_id=run.run_id)
```

---

## Notas Finais para o Codex

1. **Linguagem:** Comentarios e commits em PT-BR com acentuacao. Documentacao pode ser PT-BR.
2. **Pragmatismo:** Preferir solucoes simples que funcionam. Nao over-engineer.
3. **Atomicidade:** Tudo deve ser all-or-nothing. Delta Lake garante isso no pipeline.
4. **Testes:** TDD moderado — obrigatorio para `pipeline_lib/`, flexivel para notebooks.
5. **Secrets:** NUNCA hardcodar. Sempre via `dbutils.secrets` ou env vars.
6. **Cluster:** Pipeline roda em cluster dedicado (m5d.large), NAO em serverless.
7. **Observer separado:** A logica de IA NUNCA fica nos notebooks ETL. Observer eh um job independente.
8. **PRs do agente:** Sempre para branch `dev`, nunca para `main` diretamente.
9. **Schema evolution:** Colunas novas aceitas via `mergeSchema`, nunca rejeitadas.
10. **O pacote eh `pipeline_lib`**, nao `lib` (conflito com stdlib no Windows).
