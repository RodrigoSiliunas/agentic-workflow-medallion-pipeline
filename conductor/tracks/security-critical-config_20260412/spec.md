# Security Critical Config

## Problema
ENCRYPTION_KEY e SECRET_KEY usam defaults inseguros ("change-me..."). ENCRYPTION_KEY regenera a cada restart, destruindo credentials encriptadas. SECRET_KEY permite forja de JWT tokens.

## Solucao
1. Fail-fast no startup se ENCRYPTION_KEY ou SECRET_KEY estao com valor default
2. Gerar Fernet key + JWT secret reais e persistir no .env
3. Validar catalog name contra regex `^[a-z][a-z0-9_]{0,63}$` no catalog step (SQL injection fix)

## Escopo
- `platform/backend/app/core/security.py` — fail on default ENCRYPTION_KEY
- `platform/backend/app/core/config.py` — fail on default SECRET_KEY  
- `platform/backend/app/services/real_saga/steps/catalog.py` — validate catalog name
- `platform/backend/.env` — gerar keys reais
