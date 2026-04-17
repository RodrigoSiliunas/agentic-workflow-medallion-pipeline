# Flowertex Platform — Fluxo Completo do Sistema

## 1. Registro e Autenticacao

O usuario acessa `localhost:3000` e cria uma empresa + conta admin.

1. Frontend envia `POST /api/v1/auth/register-company` com nome da empresa, slug, email e senha
2. Backend cria a entidade `Company` (slug unico) e o `User` root com senha hasheada (bcrypt)
3. Um `Pipeline` padrao e criado automaticamente para a empresa
4. Dois tokens JWT sao gerados: **access** (15 min, no response body) e **refresh** (7 dias, httpOnly cookie)
5. Cada token carrega `jti` (UUID unico) para suportar revogacao via Redis
6. O frontend armazena o access token em `sessionStorage` e usa para todas as chamadas subsequentes
7. Quando o access expira, o composable `useApiClient` detecta 401, chama `POST /api/v1/auth/refresh` e retenta
8. No logout, ambos os tokens sao adicionados a blacklist no Redis (TTL = tempo restante do token)

---

## 2. Configuracao de Credenciais

Antes de qualquer deploy, o usuario configura credenciais em **Configuracoes**.

1. Frontend envia `POST /api/v1/settings/credentials` com tipo (anthropic, databricks, aws, github) e valor
2. Backend encripta o valor com **Fernet** (`ENCRYPTION_KEY` do .env) e salva na tabela `company_credentials`
3. As credenciais nunca trafegam em texto claro nas respostas — sempre mascaradas com `***`
4. Cada servico (DatabricksService, GitHubService, LLMOrchestrator) descriptografa sob demanda via `CredentialService`

---

## 3. Deploy One-Click (Saga Pattern)

O usuario escolhe um template de pipeline e clica "Deploy". O backend executa uma saga de 10 passos.

1. Frontend envia `POST /api/v1/deployments` com template_id e configuracoes (empresa, credenciais)
2. Backend cria registro `Deployment` com status `running` e inicia a saga em background
3. Frontend conecta via **SSE** em `GET /api/v1/deployments/{id}/events` para acompanhar progresso

**Os 10 passos da saga (RealSagaRunner):**

| # | Step | O que faz |
|---|------|-----------|
| 1 | validate | Valida credenciais (testa conexao AWS, Databricks, GitHub) |
| 2 | s3_bucket | Cria bucket S3 `{slug}-medallion-datalake` via boto3 |
| 3 | iam_role | Cria IAM role com trust policy self-assume para Unity Catalog |
| 4 | secrets | Cria secrets no Databricks Scope via Secrets API |
| 5 | catalog | Cria Unity Catalog + schemas (bronze, silver, gold) via SDK |
| 6 | upload_code | Clona repo no Databricks via Repos API (git credential + clone) |
| 7 | observer | Cria job do Observer Agent no Databricks (1 task on-demand) |
| 8 | workflow | Cria workflow ETL com 8 tasks (DAG com dependencias, cluster dedicado, cron) |
| 9 | trigger | Dispara primeira execucao via `jobs.run_now()` e faz polling ate completar |
| 10 | register | Salva `databricks_job_id` no Pipeline local e marca deployment como `completed` |

Cada passo emite eventos SSE (`step_start`, `step_complete`, `log`) que o frontend renderiza em tempo real.
O `SharedSagaState` (dataclass tipado) carrega dados entre passos (job_ids, bucket_name, role_arn, etc).

---

## 4. Pipeline ETL (Databricks)

Apos o deploy, o pipeline roda no Databricks em schedule (cron) ou sob demanda.

```
S3 (Parquet) → [pre_check] → [Bronze] → [Silver x3] → [Gold x12] → [Validation] → [observer_trigger]
```

1. **pre_check**: Verifica dados novos no S3, propaga `run_id` e `chaos_mode` via task values
2. **Bronze/ingest**: Le Parquet do S3 (via S3Lake in-memory), escreve Delta Table com overwrite atomico
3. **Silver/dedup_clean**: Deduplicacao por `conversation_id` + `sent_at`, normalizacao de campos
4. **Silver/entities_mask**: Extracao de entidades (CPF, email, phone, placa) + mascaramento PII (HMAC)
5. **Silver/enrichment**: Metricas conversacionais (duracao, mensagens, tempo resposta)
6. **Gold/analytics**: Orquestrador que dispara 12 notebooks em paralelo (funnel, sentiment, lead scoring...)
7. **Validation/checks**: Quality gates — row counts, nulls, consistencia bronze→silver→gold
8. **observer_trigger**: Task sentinel com `run_if: AT_LEAST_ONE_FAILED` — dispara Observer se houver falha

Comunicacao entre tasks via `dbutils.jobs.taskValues.set/get`. Cada notebook faz overwrite idempotente.

---

## 5. Observer Agent (Diagnostico Autonomo)

Quando o pipeline falha, o Observer analisa o erro e abre um PR com a correcao.

1. `trigger_sentinel` detecta falha e dispara o workflow `observer_agent` via Jobs API
2. `collect_and_fix` (notebook principal):
   a. `WorkflowObserver.find_recent_failures()` busca runs com falha via Jobs API
   b. `WorkflowObserver.collect_notebook_code()` le o codigo do notebook que falhou via Workspace API
   c. `WorkflowObserver.collect_schema_info()` le schemas das tabelas via Unity Catalog API
   d. `WorkflowObserver.build_context()` monta contexto completo para o LLM
3. `AnthropicProvider` envia contexto + erro para Claude (streaming) e recebe diagnostico + fix
4. `validate_fix()` roda ruff + ast.parse no fix proposto (rejeita se invalido)
5. `check_duplicate()` verifica se ja existe PR similar (hash SHA-256 do erro)
6. `GitHubProvider` cria branch `fix/agent-auto-{notebook}-{timestamp}` e abre PR para `dev`
7. CI roda automaticamente no PR (ruff + pytest)
8. GitHub Action `observer-feedback.yml` notifica o Observer quando PR e mergeado/fechado

---

## 6. Chat AI (Web)

O usuario conversa com Claude sobre seus pipelines no chat da plataforma.

1. Frontend envia `POST /api/v1/chat/threads/{id}/messages` com texto e modelo opcional
2. Backend verifica **intent** via keywords (status, erro, relatorio, fix) para economizar tokens
3. Se off-topic (sem keywords de pipeline), responde sem chamar o LLM
4. `ContextEngine.assemble()` monta system prompt + contexto do pipeline (status, schemas, runs)
5. `LLMOrchestrator.process_message()` chama Claude API com streaming (`client.messages.stream()`)
6. Claude pode usar **12 tools** (list_jobs, get_status, query_table, read_file, create_pr, etc)
7. Tools destrutivas (trigger_run, update_schedule, create_pr) pedem **confirmacao** antes de executar
8. Tokens sao emitidos via **SSE** para o frontend renderizar em tempo real
9. Apos o stream, a resposta completa e salva na tabela `messages` em uma sessao DB separada

**Modelo selecionavel**: O usuario pode trocar entre Opus (mais capaz), Sonnet (equilibrado) e Haiku (rapido).

---

## 7. Canais Externos (WhatsApp / Telegram / Discord)

Os canais externos funcionam como espelhos do chat web — mesma sessao, mesmo contexto.

### 7.1 Setup do Canal

**WhatsApp:**
1. Usuario cria instancia em `/channels` → Backend chama `POST /omni/instances` (channel: whatsapp-baileys)
2. Backend auto-conecta a instancia → Omni gera QR code
3. Backend converte QR texto → PNG base64 (lib `qrcode`) e retorna ao frontend
4. Usuario escaneia com celular → Frontend faz polling ate detectar `isActive: true`

**Telegram/Discord:**
1. Usuario cria instancia → Backend cria no Omni
2. `TokenInputModal` abre pedindo bot token (BotFather / Discord Developer Portal)
3. Backend chama `POST /omni/instances/{id}/connect` com `options.token`

### 7.2 Recebimento de Mensagens (Poller)

1. `omni_poller.py` roda como background task no lifespan do FastAPI
2. A cada 3 segundos, consulta `GET /omni/events?eventType=message.received&direction=inbound`
3. Deduplicacao via **Redis SET** (persiste entre restarts, TTL 24h)
4. Ignora: eventos pre-startup, grupos (`@g.us`), mensagens sem texto
5. Para cada evento novo, cria sessao DB e despacha para `ChannelMessageHandler`

### 7.3 Processamento da Mensagem

1. **Identidade**: Busca `ChannelIdentity` pelo phone/discord_id/telegram_id
   - Se nao vinculado: pede email → valida com regex → busca `User` → cria `ChannelIdentity`
2. **Sessao**: `_ensure_session()` sincroniza cross-channel:
   - Busca sessao do canal atual
   - Se outro canal tem sessao mais recente, sincroniza (mesmo thread/pipeline)
   - Se nenhuma sessao existe, usa o pipeline mais recente e o thread mais recente
3. **Slash commands** (`/help`, `/status`, `/resume`, `/model`, `/whoami`, etc):
   - Detectados pelo prefixo `/`
   - `/resume` sincroniza TODOS os canais do usuario para o mesmo thread
   - `/model` salva preferencia no campo `preferred_model` da `ActiveSession` (per-user, nao global)
4. **Mensagens normais**:
   - Salva mensagem do usuario na tabela `messages`
   - Carrega historico recente (20 ultimas mensagens do thread)
   - Processa via `LLMOrchestrator` (sem streaming, coleta resposta completa)
   - Salva resposta na tabela `messages`
   - Envia via `OmniService.send_message()` (chunked em 4000 chars para WhatsApp)

### 7.4 Sessao Unificada

O ponto-chave: WhatsApp, Telegram, Discord e web compartilham o **mesmo thread**.

- Perguntar algo no WhatsApp e depois "Qual era mesmo?" no Telegram funciona
- `/resume` num canal sincroniza todos os outros automaticamente
- Historico de mensagens e visivel de qualquer canal (todas gravadas no mesmo thread)

---

## 8. Infraestrutura (Docker + AWS + Terraform)

### Local (Docker Compose)

```
PostgreSQL 17  (:5432)  — banco principal (flowertex) + banco Omni (omni)
Redis 7        (:6379)  — cache, rate limiting, token revocation, poller dedup
Omni Gateway   (:8882)  — WhatsApp (Baileys) + Telegram + Discord
Backend        (:8000)  — FastAPI async
Frontend       (:3000)  — Nuxt 4 SSR
```

### AWS (via Terraform + boto3)

- **S3**: Bucket `{slug}-medallion-datalake` com lifecycle rules
- **IAM**: Role com trust policy self-assume (Unity Catalog + S3 access)
- **Secrets Manager**: Credenciais Databricks
- **Security Groups**: Regras de acesso

### Databricks

- **Unity Catalog**: `medallion` catalog com schemas bronze/silver/gold
- **Repos**: Clone do GitHub (sincronizado via CD)
- **Jobs**: Workflow ETL (8 tasks) + Observer Agent (1 task)
- **Cluster**: Dedicado (m5d.large) — serverless nao suporta S3 direct access

---

## 9. CI/CD

| Workflow | Trigger | O que faz |
|----------|---------|-----------|
| `ci.yml` | Push/PR | ruff + pytest em 4 jobs (observer, pipeline, backend, frontend) |
| `cd.yml` | Push main | Sincroniza Databricks Repo com main |
| `observer-feedback.yml` | PR merge/close em `fix/*` | Notifica Observer sobre resultado do PR |

---

## 10. Seguranca

- JWT com JTI + blacklist Redis (revogacao real no logout)
- Refresh token somente via httpOnly cookie (nunca no response body)
- Fernet encryption para credenciais de empresa
- SQL guard: bloqueia multi-statement, DDL, keywords proibidas
- Email validation com regex no onboarding de canais
- LIKE wildcards escapados em slash commands
- Security headers (X-Content-Type-Options, X-Frame-Options, Referrer-Policy)
- CORS restrito a metodos/headers especificos
- Rate limiting em auth endpoints (5/min)
- Confirmacao obrigatoria para tools destrutivas
- Docker ports bound a 127.0.0.1
- OpenAPI docs hidden em producao
