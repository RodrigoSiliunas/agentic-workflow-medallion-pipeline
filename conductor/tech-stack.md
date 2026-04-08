# Tech Stack

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

## Bibliotecas Complementares (lib/)

- `pydantic` — Validacao de contratos de schema
- `re` / `hashlib` / `hmac` — Extratores e mascaramento (stdlib)

## Opcional (Fase 5)

- `pysentimiento` — Sentimento pt-BR via BERT
- `scikit-learn` — Clusterizacao de personas (K-Means)

## Desenvolvimento Local

- `pytest` + `ruff` para testes e lint da `lib/`
- `pyspark` (dev dependency) para testes que precisam de Spark
- Dados locais em `data/conversations_bronze.parquet` (gitignored)
