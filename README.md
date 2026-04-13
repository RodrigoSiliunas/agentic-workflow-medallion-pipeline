# Safatechx Platform

Plataforma conversacional para pipelines de dados Medallion com deploy one-click, chat AI com tools em tempo real, e integração multi-canal (WhatsApp, Telegram, Discord).

## Visão Geral

```
┌─────────────────────────────────────────────────────────────────┐
│                      Safatechx Platform                         │
├──────────────┬──────────────┬──────────────┬────────────────────┤
│   Frontend   │   Backend    │  Omni Gateway│   Databricks       │
│   Nuxt 4     │   FastAPI    │  WhatsApp    │   Pipeline ETL     │
│   Vue 3      │   Claude AI  │  Telegram    │   Observer Agent   │
│   Pinia      │   PostgreSQL │  Discord     │   Delta Lake       │
│   Tailwind   │   Redis      │  Baileys     │   Unity Catalog    │
└──────────────┴──────────────┴──────────────┴────────────────────┘
```

### Principais Funcionalidades

- **Deploy One-Click**: Conecte AWS + Databricks, escolha um template de pipeline, clique Deploy
- **Chat AI**: Converse com Claude sobre seus pipelines — status, logs, dados, PRs, tudo em tempo real
- **Multi-Canal**: Mesmo chat acessível via web, WhatsApp, Telegram e Discord (sessão unificada)
- **Observer Agent**: Detecta falhas no pipeline, diagnostica com Claude, abre PR no GitHub automaticamente
- **Chaos Testing**: Injeção controlada de falhas para validar o agente end-to-end

## Arquitetura

```
                    ┌─────────────┐
                    │   Frontend  │ :3000
                    │   Nuxt 4    │
                    └──────┬──────┘
                           │ REST API
                    ┌──────┴──────┐
                    │   Backend   │ :8000
                    │   FastAPI   │
                    └──┬───┬───┬──┘
                       │   │   │
              ┌────────┘   │   └────────┐
              │            │            │
       ┌──────┴──┐  ┌──────┴──┐  ┌──────┴──────┐
       │Postgres │  │  Redis  │  │Omni Gateway │ :8882
       │  :5432  │  │  :6379  │  │ WhatsApp    │
       └─────────┘  └─────────┘  │ Telegram    │
                                 │ Discord     │
                                 └─────────────┘

  ┌──────────────────────────────────────────────────────────┐
  │                        AWS                                │
  │  ┌──────────────────────────────────────────────┐        │
  │  │              Databricks                      │        │
  │  │  Pipeline ETL      │   Observer Agent        │        │
  │  │  Bronze→Silver→Gold│   Claude → GitHub PR    │        │
  │  └──────────────────────────────────────────────┘        │
  │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐       │
  │  │  S3      │  │  IAM     │  │ Secrets Manager  │       │
  │  │ Datalake │  │ Roles    │  │ Credentials      │       │
  │  └──────────┘  └──────────┘  └──────────────────┘       │
  └──────────────────────────────────────────────────────────┘
```

## Quick Start (Docker)

### Pré-requisitos

- [Docker](https://docs.docker.com/get-docker/) + Docker Compose
- [Bun](https://bun.sh/) (para dev do frontend)
- Conta AWS + Databricks (para o pipeline — opcional para testar a plataforma)

### 1. Clonar e configurar

```bash
git clone https://github.com/RodrigoSiliunas/agentic-workflow-medallion-pipeline.git
cd agentic-workflow-medallion-pipeline
```

### 2. Configurar variáveis de ambiente

```bash
# Backend
cp platform/backend/.env.example platform/backend/.env
# Editar com seus valores: SECRET_KEY, ENCRYPTION_KEY, OMNI_API_KEY, etc.

# Pipeline (opcional)
cp .env.example .env
# Editar: DATABRICKS_HOST, DATABRICKS_TOKEN, AWS keys, ANTHROPIC_API_KEY
```

**Gerar chaves de segurança:**

```bash
# SECRET_KEY (JWT)
python -c "import secrets; print(secrets.token_hex(64))"

# ENCRYPTION_KEY (Fernet)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# OMNI_API_KEY (formato Omni)
echo "omni_sk_$(openssl rand -base64 24 | tr -d '/+=')"
```

### 3. Subir os serviços

```bash
cd platform/backend

# Subir PostgreSQL + Redis + Omni Gateway
docker compose up -d postgres redis omni

# Aguardar health checks
docker compose ps  # todos devem estar "healthy"

# Rodar migrations do backend
uv sync
uv run alembic upgrade head

# Iniciar backend (dev)
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

```bash
# Em outro terminal — Frontend
cd platform/frontend
bun install
bun run dev  # http://localhost:3000
```

### 4. Primeiro acesso

1. Abra `http://localhost:3000`
2. Registre uma empresa + usuário admin
3. Vá em **Configurações** → adicione suas credenciais (Anthropic, Databricks, AWS, GitHub)
4. Vá em **Templates** → escolha o pipeline → **Deploy**
5. Vá em **Chat** → converse com Claude sobre seu pipeline
6. Vá em **Channels** → conecte WhatsApp/Telegram/Discord

### 5. Conectar canais

**WhatsApp:**
- Channels → Nova instância → WhatsApp → Criar
- Escaneie o QR code com seu celular

**Telegram:**
- Crie um bot no @BotFather → copie o token
- Channels → Nova instância → Telegram → Criar → Cole o token

**Discord:**
- Crie um app no [Discord Developer Portal](https://discord.com/developers)
- Bot → ative Privileged Intents (Message Content, Server Members, Presence)
- OAuth2 → scope `bot` → permissões: Send Messages, Read History, View Channels
- Channels → Nova instância → Discord → Criar → Cole o bot token

## Estrutura do Monorepo

```
├── observer-framework/          # Framework genérico de observabilidade
│   ├── observer/                # Pacote Python (config, dedup, providers, workflow)
│   ├── notebooks/               # Notebooks Databricks (collect_and_fix, trigger)
│   ├── deploy/                  # Script de deploy do Observer
│   └── tests/                   # 113 testes pytest
│
├── pipelines/
│   └── pipeline-seguradora-whatsapp/  # Template: pipeline WhatsApp seguros
│       ├── notebooks/           # Bronze → Silver → Gold → Validation
│       ├── pipeline_lib/        # Lib Python (extractors, masking, schema, S3)
│       ├── deploy/              # Scripts de deploy (workflow, catalog, chaos)
│       └── tests/               # 91 testes pytest
│
├── platform/
│   ├── frontend/                # Nuxt 4 + Vue 3 + TypeScript
│   │   ├── app/components/      # Atomic Design (atoms/molecules/organisms)
│   │   ├── app/stores/          # Pinia stores
│   │   ├── app/composables/     # API clients (mock/real strategy)
│   │   └── Dockerfile           # Multi-stage: Bun build + Node runtime
│   │
│   ├── backend/                 # FastAPI async
│   │   ├── app/api/routes/      # Auth, chat, channels, deployments, etc.
│   │   ├── app/services/        # LLM orchestrator, Omni, channel handler
│   │   ├── app/models/          # SQLAlchemy 2 async models
│   │   ├── docker-compose.yml   # Postgres + Redis + Omni + Backend
│   │   └── Dockerfile           # Multi-stage: uv + Python 3.12
│   │
│   └── design/                  # Design system references
│
├── infra/aws/                   # Terraform (IAM, S3, Security Groups)
│   ├── 01-foundation/           # IAM users/roles, SGs, Secrets Manager, S3 root
│   └── 02-datalake/             # S3 datalake com lifecycle rules
│
├── .github/workflows/           # CI (ruff + pytest) + CD (Databricks sync)
└── CLAUDE.md                    # Instruções para AI assistants
```

## Tech Stack

| Camada | Tecnologia |
|--------|-----------|
| Frontend | Nuxt 4.4, Vue 3, TypeScript, Pinia, Tailwind, @nuxt/ui |
| Backend | FastAPI, SQLAlchemy 2 async, Pydantic, httpx |
| Database | PostgreSQL 17, Redis 7 |
| AI | Claude API (Opus/Sonnet/Haiku), streaming, tool use |
| Mensageria | Omni Gateway (Baileys, Discord.js, Telegram Bot API) |
| Pipeline | PySpark, Delta Lake, Unity Catalog, Databricks SDK |
| Infra | Terraform, boto3, Docker Compose |
| CI/CD | GitHub Actions, Databricks Repos sync |
| Testes | pytest (204 testes), Vitest, Playwright |

## Chat AI com Tools

O chat usa Claude com 12 tools que acessam dados reais:

| Tool | O que faz |
|------|-----------|
| `list_databricks_jobs` | Lista todos os jobs com IDs |
| `get_job_details` | Configuração completa (cron, tasks, timeout) |
| `get_pipeline_status` | Status atual e última execução |
| `get_run_logs` | Logs detalhados de uma run |
| `query_delta_table` | SELECT SQL em tabelas Delta |
| `get_table_schema` | Schema de todas as tabelas |
| `read_file` | Lê arquivos do repositório |
| `list_recent_prs` | PRs recentes (inclui auto-fixes) |
| `get_pr_diff` | Diff de um PR específico |
| `update_job_schedule` | Altera cron do job (com confirmação) |
| `update_job_settings` | Altera timeout/tags (com confirmação) |
| `trigger_pipeline_run` | Dispara execução (com confirmação) |

## Slash Commands (WhatsApp/Telegram/Discord)

```
/help                    — lista todos os comandos
/pipelines               — listar pipelines disponíveis
/resume [pipeline]       — conectar a um pipeline
/resume [pipeline] [uuid]— retomar conversa específica
/new [pipeline]          — nova conversa
/status                  — status do pipeline ativo
/threads [pipeline]      — listar conversas
/model [opus|sonnet|haiku] — trocar modelo do Claude
/whoami                  — info da sessão (canal, pipeline, thread UUID)
```

## Desenvolvimento

```bash
# Backend
cd platform/backend
uv sync --dev
uv run pytest tests/ -v         # testes
uv run ruff check app/          # lint

# Frontend
cd platform/frontend
bun install
bun run dev                     # dev server
bun run lint                    # lint
bun run test                    # testes

# Pipeline (requer Databricks)
cd pipelines/pipeline-seguradora-whatsapp
pip install -e ".[dev]"
pytest tests/ -v

# Observer Framework
cd observer-framework
pip install -e ".[dev]"
pytest tests/ -v
```

## Variáveis de Ambiente

### Backend (`platform/backend/.env`)

| Variável | Descrição |
|----------|-----------|
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `SECRET_KEY` | JWT signing key (hex 64 chars) |
| `ENCRYPTION_KEY` | Fernet key para credenciais |
| `OMNI_API_URL` | URL do Omni Gateway |
| `OMNI_API_KEY` | API key do Omni |
| `OMNI_WEBHOOK_SECRET` | HMAC secret para webhooks |
| `DEBUG` | true/false (habilita docs OpenAPI) |
| `AUTO_SEED` | true/false (seed templates no startup) |

### Pipeline (`.env` na raiz)

| Variável | Descrição |
|----------|-----------|
| `DATABRICKS_HOST` | URL do workspace Databricks |
| `DATABRICKS_TOKEN` | PAT token do Databricks |
| `AWS_ACCESS_KEY_ID` | AWS IAM access key |
| `AWS_SECRET_ACCESS_KEY` | AWS IAM secret key |
| `ANTHROPIC_API_KEY` | Claude API key |
| `GITHUB_TOKEN` | GitHub PAT (classic, para Repos API) |

## Licença

MIT
