# Agentic Workflow Medallion Pipeline

Pipeline agentico de transformacao de dados Medallion (Bronze → Silver → Gold) sobre conversas WhatsApp de vendas de seguro automotivo, rodando no **Databricks + AWS**.

## Arquitetura

```
Databricks Workflow (cron diario, max_concurrent_runs=1)

Task 0: Agent Pre-Check     → verifica dados novos, captura versoes Delta
Task 1: Bronze Ingestion    → Parquet cru → Delta Table (schema evolution)
Task 2a: Silver Dedup       → dedup sent+delivered, normalizacao, metadata
Task 2b: Silver Entities    → extracao CPF/email/placa + mascaramento + redaction (paralela)
Task 2c: Silver Enrichment  → metricas por conversa (paralela com 2b)
Task 3: Gold Analytics      → 12 tabelas analiticas (orquestrador)
Task 4: Quality Validation  → checks de integridade Bronze→Silver→Gold
Task 5: Agent Post-Check    → recovery, rollback Delta, notificacoes email
```

## Dados

- **Fonte**: ~15k conversas WhatsApp, 153k mensagens, seguro automotivo, pt-BR
- **Periodo**: Fevereiro 2026
- **Formato**: Parquet → Delta Lake (ACID, time travel, schema evolution)

## Tech Stack

| Componente | Tecnologia |
|------------|-----------|
| Plataforma | Databricks Free Edition (AWS) |
| Engine | PySpark |
| Storage | Delta Lake + Unity Catalog |
| Orquestracao | Databricks Workflows |
| Testes | pytest (89 testes) |
| Lint | ruff |
| CI | GitHub Actions |

## Estrutura do Projeto

```
notebooks/                  # Notebooks Databricks
  agent_pre.py              # Task 0: pre-check
  agent_post.py             # Task 5: post-check + recovery + email
  bronze/ingest.py          # Ingestao Parquet → Delta
  silver/dedup_clean.py     # Dedup + normalizacao
  silver/entities_mask.py   # Extracao + mascaramento + redaction
  silver/enrichment.py      # Metricas por conversa
  gold/analytics.py         # Orquestrador (12 tabelas)
  gold/funnel.py            # Funil de conversao
  gold/sentiment.py         # Sentimento (heuristica)
  gold/sentiment_ml.py      # Sentimento (pysentimiento BERT)
  gold/lead_scoring.py      # Score 0-100
  gold/agent_performance.py # Ranking de vendedores
  ...                       # + 8 tabelas analiticas
  validation/checks.py      # Quality checks

pipeline_lib/               # Codigo Python puro (testavel localmente)
  extractors/               # CPF, email, phone, plate, CEP, vehicle, competitor, price
  masking/                  # Format-preserving, HMAC hash, redaction
  schema/                   # Validacao com schema evolution

deploy/                     # Scripts de deploy
  setup_catalog.py          # Cria Unity Catalog + schemas
  upload_data.py            # Upload Parquet para Volumes
  create_workflow.py        # Cria Workflow via SDK
  trigger_run.py            # Dispara execucao manual
  dashboard_queries.sql     # Queries para Dashboard + Alerts

tests/                      # 89 testes (pytest)
```

## Gold Layer: 12 Tabelas Analiticas

| Tabela | Insight |
|--------|---------|
| `funil_vendas` | Outcomes + mensagem fatal antes de ghosting |
| `agent_performance` | Scoring com percentis entre 20 agentes |
| `sentiment` | Sentimento por conversa (-1.0 a +1.0) |
| `lead_scoring` | Score 0-100 (hot/warm/cold) |
| `email_providers` | Distribuicao Gmail vs Outlook vs Yahoo |
| `temporal_analysis` | Heatmap hora x dia x conversao |
| `competitor_intel` | Concorrentes, price gap, loss rate |
| `campaign_roi` | Eficacia das 10 campanhas + analise geografica |
| `personas` | 6 personas comportamentais |
| `churn_reengagement` | Deteccao de silencio > 2h e reativacao |
| `negotiation_complexity` | Perguntas preco vs cobertura vs outcome |
| `first_contact_resolution` | % vendas na 1a conversa vs recontato |

## Agente Autonomo

- **Pre-check**: verifica dados novos via fingerprint, captura versoes Delta
- **Post-check**: verifica resultados, tenta recovery (rollback Delta), notifica
- **Guardrail**: para apos 3 falhas consecutivas
- **Emails**: sucesso (resumo), correcao (detalhes), falha (critico)
- **Observabilidade**: Delta Tables de metricas + estado + notificacoes, Dashboard SQL, Alerts

## Setup e Deploy

### Pre-requisitos

- Databricks Workspace (Free Edition ou superior) com AWS
- Unity Catalog habilitado
- Python 3.11+

### Passo a passo

```bash
# 1. Clonar o repositorio
git clone https://github.com/seu-usuario/agentic-workflow-medallion-pipeline.git
cd agentic-workflow-medallion-pipeline

# 2. Configurar .env
cp .env.example .env
# Editar: DATABRICKS_HOST, DATABRICKS_TOKEN, MASKING_SECRET

# 3. Instalar dependencias (dev local)
python -m venv .venv
source .venv/bin/activate  # ou .venv\Scripts\activate no Windows
pip install -e ".[dev]"

# 4. Rodar testes
pytest tests/ -v

# 5. Setup Databricks
export $(cat .env | xargs)
python deploy/setup_catalog.py
python deploy/upload_data.py conversations_bronze.parquet

# 6. Conectar Databricks Repos ao GitHub
# No Databricks: Repos > Add Repo > URL do GitHub

# 7. Criar e executar Workflow
python deploy/create_workflow.py
python deploy/trigger_run.py <job_id>
```

## Testes

```bash
pytest tests/ -v          # 89 testes
ruff check .              # Lint
```

## Dados Sensiveis

- CPF, email, telefone, placa mascarados na Silver (format-preserving)
- `message_body` sofre redaction (PII substituido por versao mascarada)
- Chave HMAC obrigatoria via `MASKING_SECRET` (sem fallback)
- Bronze com dados originais: acesso restrito via Unity Catalog
