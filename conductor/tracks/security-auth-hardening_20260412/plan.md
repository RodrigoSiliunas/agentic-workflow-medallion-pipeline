# Plan: Security Auth Hardening

## Phase 1: Quick wins
- [ ] Task 1: webhooks.py — rejeitar se OMNI_WEBHOOK_SECRET vazio (503)
- [ ] Task 2: auth.py refresh — verificar user existe e is_active antes de emitir tokens
- [ ] Task 3: credential_service.py — validar databricks_host contra regex `^https://.*\.cloud\.databricks\.com`
- [ ] Task 4: auth schemas — adicionar min_length=8 no password

## Phase 2: Rate limiting
- [ ] Task 5: Aplicar RateLimiter como dependency em /auth/login, /auth/register-company, /webhooks/omni
