# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Monorepo Structure

```
pipeline/           — Pipeline Medallion (Databricks + AWS)
platform/frontend/  — Plataforma Conversacional (Nuxt 4.4.2 + Vue 3)
platform/backend/   — API da Plataforma (FastAPI — padrao idlehub)
platform/design/    — Design system references (awesome-design-md)
docs/               — Analise arquitetural, viabilidade, spec plataforma
conductor/          — Tracks e workflow do projeto
```

## Pipeline (pipeline/)

Agentic Medallion pipeline: Bronze → Silver → Gold sobre conversas WhatsApp de seguro auto.

- **Plataforma**: Databricks Free Edition (AWS), Unity Catalog, Delta Lake
- **Engine**: PySpark
- **Agente**: agent_pre.py (Task 0) + agent_post.py (Task 5) com Claude API + auto-PR GitHub
- **Testes**: 89 testes (pytest), ruff lint
- **Deploy**: Scripts em pipeline/deploy/ (setup_catalog, create_workflow, upload_data, trigger_run)

## Platform Frontend (platform/frontend/)

- **Framework**: Nuxt 4.4.2 + Vue 3 + TypeScript
- **Package manager**: Bun
- **UI**: @nuxt/ui (Tailwind-based)
- **Estado**: Pinia
- **Composables**: @vueuse/nuxt
- **Arquitetura de componentes**: **Atomic Design**
  - `atoms/` — Elementos indivisiveis (Button, Input, Badge). Zero logica de negocio.
  - `molecules/` — Combinacao de atoms (SearchBar, MessageBubble). Estado local simples.
  - `organisms/` — Secoes completas (ChatWindow, Sidebar). Usam composables e stores.
  - `templates/` — Layouts de pagina (ChatLayout, AuthLayout).
  - Ver `ATOMIC_DESIGN.md` para guia completo.
- **Padroes do idlehub a seguir**: useApiClient com token refresh, SWR caching, auth middleware global

## Platform Backend (platform/backend/)

- **Framework**: FastAPI (async)
- **Padrao**: Baseado no idlehub-platform-backend
- **Auth**: JWT + API Key, RBAC (viewer/editor/admin), multi-tenant
- **DB**: PostgreSQL (SQLAlchemy 2 async)
- **Cache**: Redis
- **Padroes**: Service layer, domain exceptions, Pydantic Settings, lifespan hooks

## Convencoes

- **Commits**: Conventional Commits em pt-BR (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`)
- **Lint Python**: ruff (line-length=100, py311). Notebooks excluidos.
- **Lint JS/TS**: ESLint flat config + Prettier (double quotes, 2 spaces, 100 chars)
- **Testes Python**: pytest. TDD moderado (obrigatorio para lib/, flexivel para notebooks)
- **Testes JS**: Vitest + Vue Test Utils
- **Branch strategy**: PRs do agente AI para `dev` (fix/usuario/..., feat/usuario/...)
- **Dados sensiveis**: Mascaramento na Silver, HMAC obrigatorio sem fallback, redaction do message_body
