# Tech Stack

## Monorepo Layout

- `observer-framework/` — Framework reusavel (pacote Python `observer`, futuro repo open-source)
- `pipelines/pipeline-seguradora-whatsapp/` — Pipeline WhatsApp de seguro auto (primeiro template para one-click deploy futuro)
- `platform/` — Plataforma conversacional (Nuxt frontend + FastAPI backend)
- `infra/aws/` — Terraform (01-foundation + 02-datalake)
- `conductor/` — Tracks e workflow do monorepo
- `docs/` — Análise arquitetural
- `.github/workflows/` — CI (jobs separados para observer e pipeline) + CD (sync Databricks Repo) + observer-feedback

Zero interdependência entre observer-framework e pipeline: o pipeline apenas referencia notebooks do framework via path absoluto no Databricks Repo, sem import Python.

## Core Platform

| Componente | Tecnologia | Papel |
|------------|-----------|-------|
| **Plataforma** | Databricks Workspace (AWS) | Ambiente de execucao, Workflows, Unity Catalog |
| **Storage** | AWS S3 | Data lake: `/bronze/` (Parquet cru), `/silver/`, `/gold/` (Delta Tables) |
| **Engine** | PySpark (Databricks Runtime) | Processamento de dados distribuido |
| **Formato** | Delta Lake | ACID, schema evolution, time travel, audit |
| **Orquestracao** | Databricks Workflows | DAG de tasks com cron diario, retries, alertas |
| **Governanca** | Unity Catalog | Schema registry, linhagem, controle de acesso |

## Linguagem e Ferramentas

| Componente | Tecnologia | Versao |
|------------|-----------|--------|
| **Linguagem** | Python | >= 3.11 |
| **Validacao** | Pydantic | >= 2.0 |
| **Testes** | pytest | >= 8.0 |
| **Linting/Format** | ruff | >= 0.4 |
| **Deploy** | Databricks Repos | Sync com GitHub |

## Bibliotecas no Databricks (pre-instaladas)

- `pyspark` — DataFrame API + SQL
- `delta` — Delta Lake Python API
- `dbutils` — Comunicacao entre tasks, filesystem, secrets
- `logging` — Logs nativos capturados pelo Databricks

## Bibliotecas Complementares

**observer-framework/observer/**:
- `pydantic` — ObserverConfig + validacao de providers
- `pyyaml` — Load de observer_config.yaml
- `databricks-sdk` — Jobs/Workspace/UnityCatalog APIs
- `anthropic` / `openai` / `PyGithub` — opcionais via extras

**pipelines/pipeline-seguradora-whatsapp/pipeline_lib/**:
- `pydantic` — Validacao de contratos de schema
- `re` / `hashlib` / `hmac` — Extratores e mascaramento (stdlib)

## Opcional (ML, Pipeline)

- `pysentimiento` — Sentimento pt-BR via BERT
- `scikit-learn` — Clusterizacao de personas (K-Means)

## Desenvolvimento Local

- `pytest` + `ruff` para testes e lint de ambos os projetos
- `pyspark` (dev dependency) para testes que precisam de Spark
- Dados locais em `pipelines/pipeline-seguradora-whatsapp/data/conversations_bronze.parquet` (gitignored)
