# Implementation Plan: Platform Backend (FastAPI)

**Track ID:** platform-backend_20260408
**Spec:** [spec.md](./spec.md)
**Created:** 2026-04-08
**Status:** [ ] Not Started

## Overview

Implementar backend FastAPI com auth multi-tenant (IAM), settings de empresa com credenciais criptografadas, chat SSE, Context Engine, LLM com tools, webhook Omni, e management automatizado de canais.

## Phase 1: Project Scaffolding + Auth + DB

### Tasks

- [ ] Task 1.1: Scaffold FastAPI (padrao idlehub: main.py, config.py, deps.py, routers/, services/, models/, schemas/)
- [ ] Task 1.2: Pydantic Settings com cascade .env (DATABASE_URL, REDIS_URL, JWT secrets, ENCRYPTION_KEY)
- [ ] Task 1.3: PostgreSQL + SQLAlchemy 2 async (models: companies, users, company_credentials)
- [ ] Task 1.4: Alembic migrations
- [ ] Task 1.5: AuthContext dataclass (user, company, role, permissions)
- [ ] Task 1.6: Auth routes: POST /auth/login, /auth/refresh, /auth/register-company (cria empresa + root user)
- [ ] Task 1.7: JWT (access 15min, refresh 7d) + bcrypt passwords + Fernet encryption para credenciais
- [ ] Task 1.8: RBAC middleware: root > admin > editor > viewer
- [ ] Task 1.9: User management routes: POST /users (admin cria), GET /users, PUT /users/:id/role

### Verification

- [ ] Login/refresh funciona, JWT valido
- [ ] Root cria empresa, admin cria usuarios
- [ ] Viewer nao acessa settings, editor nao cria usuarios
- [ ] Testes auth passando

## Phase 2: Company Settings + Credential Management

### Tasks

- [ ] Task 2.1: Models: company_credentials (company_id, type, encrypted_value, is_valid, last_tested_at)
- [ ] Task 2.2: Fernet encryption service (encrypt/decrypt, chave separada do JWT)
- [ ] Task 2.3: Routes: GET/PUT /settings/credentials (root/admin only)
- [ ] Task 2.4: Credential types: anthropic_api_key, discord_bot_token, telegram_bot_token, github_token, github_repo, databricks_host, databricks_token
- [ ] Task 2.5: Validacao no save: test Anthropic API call, test Databricks connection, test GitHub repo access
- [ ] Task 2.6: WhatsApp QR Code: route que proxeia Omni WebSocket para o frontend
- [ ] Task 2.7: Testes: credential CRUD, encryption round-trip, validation mocks

### Verification

- [ ] Admin salva Anthropic key → test call passa → armazenada criptografada
- [ ] Admin salva Databricks token → test connection → OK
- [ ] Viewer tenta acessar settings → 403
- [ ] Credencial descriptografada corretamente quando usada pelo Context Engine

## Phase 3: Pipeline Registration + Context Engine

### Tasks

- [ ] Task 3.1: Models: pipelines, pipeline_context_cache
- [ ] Task 3.2: Routes: CRUD /pipelines (admin registra, todos veem)
- [ ] Task 3.3: Databricks Service: get_status, list_runs, get_logs, query_table, trigger_run (usa credencial da empresa)
- [ ] Task 3.4: Context Engine: collect, rank, assemble (3 niveis: resumo, detalhes, completo)
- [ ] Task 3.5: Intent classifier (heuristica por keywords: status_check, error_diagnosis, change_request, report_request)
- [ ] Task 3.6: Cache Redis L1 (pipeline_state 60s, schemas 300s, runs 120s)
- [ ] Task 3.7: Testes: context assembly, cache invalidation, mock Databricks responses

### Verification

- [ ] Pipeline registrado, status consultado via Databricks SDK com credencial da empresa
- [ ] Context Engine monta prompt de 3 niveis corretamente
- [ ] Cache funciona (segunda chamada < 10ms)

## Phase 4: Chat + LLM Orchestrator + Tools

### Tasks

- [ ] Task 4.1: Models: threads, messages
- [ ] Task 4.2: Routes: POST /chat/message (SSE stream), GET /chat/threads, POST /chat/threads, DELETE
- [ ] Task 4.3: LLM Orchestrator: loop de tool use (max 10 rounds), streaming SSE
- [ ] Task 4.4: Tools: get_pipeline_status, get_run_logs, query_delta_table, get_table_schema
- [ ] Task 4.5: Tools: create_pull_request, trigger_pipeline_run, send_notification (requerem confirmacao)
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
- [ ] Task 5.2: Route: POST /webhooks/omni (recebe mensagens normalizadas do Omni)
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

- [ ] Task 6.1: Rate limiting Redis-backed (sliding window, por empresa, com fallback in-memory)
- [ ] Task 6.2: Middleware: RequestID, CORS, GZip
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
