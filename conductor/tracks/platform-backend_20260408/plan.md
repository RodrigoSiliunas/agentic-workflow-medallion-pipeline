# Implementation Plan: Platform Backend (FastAPI)

**Track ID:** platform-backend_20260408
**Spec:** [spec.md](./spec.md)
**Created:** 2026-04-08
**Status:** [~] In Progress

## Overview

Implementar backend FastAPI com auth multi-tenant (IAM), settings de empresa com credenciais criptografadas, chat SSE, Context Engine, LLM com tools, webhook Omni, e management automatizado de canais.

## Phase 1: Project Scaffolding + Auth + DB

### Tasks

- [x] Task 1.1: Scaffold FastAPI (main.py, config.py, deps.py, routers/, services/, models/, schemas/)
- [x] Task 1.2: Pydantic Settings com cascade .env (DATABASE_URL, REDIS_URL, JWT secrets, ENCRYPTION_KEY)
- [x] Task 1.3: PostgreSQL + SQLAlchemy 2 async (models: companies, users, company_credentials)
- [x] Task 1.4: Alembic migrations (PostgreSQL + initial_schema: 4 tabelas)
- [x] Task 1.5: AuthContext dataclass (user, company, role, permissions)
- [x] Task 1.6: Auth routes: POST /auth/login, /auth/refresh, /auth/register-company
- [x] Task 1.7: JWT HS256 (access 15min, refresh 7d) + bcrypt + Fernet encryption (chave separada)
- [x] Task 1.8: RBAC: root > admin > editor > viewer (require_permission, require_role)
- [x] Task 1.9: User management routes: POST /users, GET /users, PUT /users/:id/role
- [x] Task 1.10: Audit log model (who, what, when, channel, ip) + domain exceptions

### Verification

- [ ] Login/refresh funciona, JWT valido
- [ ] Root cria empresa, admin cria usuarios
- [ ] Viewer nao acessa settings, editor nao cria usuarios
- [ ] Testes auth passando

## Phase 2: Company Settings + Credential Management

### Tasks

- [x] Task 2.1: Model CompanyCredential (criado na Phase 1)
- [x] Task 2.2: EncryptionService (Fernet, chave separada do JWT)
- [x] Task 2.3: Routes: GET /settings, PUT /credentials, POST /credentials/:type/test
- [x] Task 2.4: 7 credential types (anthropic, discord, telegram, github, databricks)
- [x] Task 2.5: Validacao: test Anthropic API, Databricks conn, GitHub repo
- [ ] Task 2.6: WhatsApp QR Code SSE (implementar com Omni na Phase 5)
- [x] Task 2.7: PUT /settings/preferred-model (sonnet/opus)
- [ ] Task 2.8: Testes credential (pendente)

### Verification

- [ ] Admin salva Anthropic key → test call passa → armazenada criptografada
- [ ] Admin salva Databricks token → test connection → OK
- [ ] Viewer tenta acessar settings → 403
- [ ] Credencial descriptografada corretamente quando usada pelo Context Engine

## Phase 3: Pipeline Registration + Context Engine

### Tasks

- [x] Task 3.1: Models: Pipeline + PipelineContextCache + migration aplicada
- [x] Task 3.2: Routes: GET /pipelines, POST /pipelines, GET /pipelines/:id/status
- [x] Task 3.3: DatabricksService: get_job_status, list_runs, get_run_output, query_table, trigger_run, get_table_schemas, get_pipeline_summary
- [x] Task 3.4: Context Engine: 3 niveis (resumo/detalhes/completo), auto-select por intent
- [x] Task 3.5: Intent classifier: 5 intents (status_check, error_diagnosis, change_request, report_request, fix_request) + priority weights
- [ ] Task 3.6: Cache Redis L1 + PostgreSQL L2 (implementar na Phase 6 com Redis)
- [x] Task 3.7: GitHubService: read_file, list_recent_prs, create_pr (usa credencial da empresa)
- [ ] Task 3.8: Testes (pendente)

### Verification

- [ ] Pipeline registrado, status consultado via Databricks SDK com credencial da empresa
- [ ] Context Engine monta prompt de 3 niveis corretamente
- [ ] Cache funciona (segunda chamada < 10ms)

## Phase 4: Chat + LLM Orchestrator + Tools

### Tasks

- [ ] Task 4.1: Models: threads, messages
- [ ] Task 4.2: Routes: POST /chat/message (SSE stream), GET /chat/threads, POST /chat/threads, DELETE
- [ ] Task 4.3: LLM Orchestrator: loop de tool use (max 10 rounds), streaming SSE
- [ ] Task 4.4: Tools leitura: get_pipeline_status, get_run_logs, query_delta_table, get_table_schema, read_file, list_recent_prs
- [ ] Task 4.5: Tools acao: create_pull_request, trigger_pipeline_run, send_notification, generate_chart_data (requerem confirmacao exceto chart)
- [ ] Task 4.5b: Email notification service (SES ou SendGrid, configuravel por empresa)
- [ ] Task 4.6: Confirmacao inline: tool retorna "confirmation_required", frontend mostra botao
- [ ] Task 4.7: Historico de conversa: ultimas 20 mensagens completas, 21-50 resumidas
- [ ] Task 4.8: Testes: chat flow, tool execution mocks, SSE streaming

### Verification

- [ ] Usuario envia mensagem, recebe resposta streaming via SSE
- [ ] LLM chama tools corretamente (query_table retorna dados reais)
- [ ] Acoes perigosas pedem confirmacao
- [ ] Historico persiste entre sessoes

## Phase 5: Webhook Omni + Slash Commands + Channel Management

### Tasks

- [ ] Task 5.1: Omni Service: create_instance, connect, configure_webhook, send_message (usa Omni API)
- [ ] Task 5.2: Route: POST /webhooks/omni (recebe mensagens normalizadas) com HMAC signature validation
- [ ] Task 5.2b: Route: POST /webhooks/pipeline (recebe eventos do agent_pre/agent_post para notificacoes proativas)
- [ ] Task 5.2c: Multi-tenant instance naming: company_{slug}_{channel} (ex: acme_whatsapp, acme_discord)
- [ ] Task 5.3: Channel identity resolver: identifica usuario por phone/discord_id/telegram_id
- [ ] Task 5.4: Slash command parser: /resume, /pipelines, /status, /threads, /new, /whoami, /help
- [ ] Task 5.5: Models: active_sessions, channel_identities
- [ ] Task 5.6: Cross-channel: /resume [pipeline] [uuid] retoma thread de outro canal
- [ ] Task 5.7: Auto-setup canais: quando admin salva Discord token em settings, backend chama Omni API para criar instancia
- [ ] Task 5.8: WhatsApp QR: POST /settings/whatsapp/pair → inicia pairing via Omni → retorna QR stream
- [ ] Task 5.9: Testes: webhook handler, slash commands, channel identity, cross-channel resume

### Verification

- [ ] Mensagem do WhatsApp chega via Omni → backend processa → resposta volta pelo Omni
- [ ] /resume funciona cross-channel (WhatsApp → Discord)
- [ ] Admin configura Discord token → instancia criada automaticamente no Omni
- [ ] QR Code do WhatsApp aparece na pagina de settings

## Phase 6: Rate Limiting + Observability + Polish

### Tasks

- [ ] Task 6.1: Rate limiting Redis-backed (sliding window, por empresa + por canal, com fallback in-memory)
- [ ] Task 6.1b: Rate limits por canal: WhatsApp 1500msg/dia, Discord 50req/s, Telegram 30msg/s
- [ ] Task 6.2: Middleware: RequestID, CORS, GZip
- [ ] Task 6.2b: Route GET /health/channels — status de todas as instancias Omni da empresa
- [ ] Task 6.3: Domain exceptions: NotFound→404, Conflict→409, AuthorizationError→403, PlanLimit→402
- [ ] Task 6.4: Prometheus metrics endpoint (/metrics)
- [ ] Task 6.5: Structured logging (JSON em producao)
- [ ] Task 6.6: Lifespan hooks (startup: Redis, Omni health check; shutdown: cleanup)
- [ ] Task 6.7: Dockerfile + docker-compose (backend + PostgreSQL + Redis + Omni)

### Verification

- [ ] Rate limit funciona (6a requisicao em 60s retorna 429)
- [ ] docker-compose up sobe todos os servicos
- [ ] Logs em JSON, metricas Prometheus, RequestID propagado

## Final Verification

- [ ] Auth multi-tenant funciona (2 empresas isoladas)
- [ ] Chat web funciona com SSE
- [ ] Canal externo (WhatsApp/Discord) funciona via Omni
- [ ] Cross-channel resume funciona
- [ ] PRs criados com branch do usuario, base dev
- [ ] Credenciais criptografadas, nunca em logs
- [ ] Testes passando, lint limpo

---

_Generated by Conductor._
