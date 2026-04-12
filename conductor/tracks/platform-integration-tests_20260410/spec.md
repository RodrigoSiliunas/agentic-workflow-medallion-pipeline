# Specification: Integration Tests

**Track ID:** platform-integration-tests_20260410
**Status:** Complete

## Summary

Suite de integration tests com `httpx.AsyncClient` + `ASGITransport` + Postgres real (DB `namastex_test` no container docker). Cobre auth, templates, deployments, channels, observability.

## Entrega

### Infraestrutura

- `tests/integration/conftest.py` com:
  - `test_engine` session-scoped (drop+create schema)
  - `_truncate_all_tables` autouse yield-trucate-all pra isolar
  - `http_client` via `ASGITransport` com `get_db` override
  - `registered_company` / `auth_headers` fixtures
- `pyproject.toml`:
  - `asyncio_default_fixture_loop_scope = "session"` (fixa o bug "different loop")
  - `asyncio_default_test_loop_scope = "session"`

### Tests (14 novos)

- `test_auth.py` (3): register + /users/me + default pipeline, wrong password, duplicate slug
- `test_templates.py` (4): list vazio, list apos seed, get by slug, 404
- `test_deployments.py` (3): list vazio, create com template, create template 404
- `test_channels.py` (3): list vazio, create sem Omni → failed, invalid kind 422
- `test_observability.py` (1): metrics shape

## Total

**49 tests passing** (35 unit + 14 integration)

## Prerequisitos

- Docker rodando (`namastex-postgres`)
- `CREATE DATABASE namastex_test` ja feito (uma vez)
