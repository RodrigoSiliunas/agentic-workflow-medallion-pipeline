# Security Auth Hardening

## Problema
- Webhook HMAC validation bypassed quando OMNI_WEBHOOK_SECRET vazio
- JWT tokens em localStorage (vulneravel a XSS)
- Refresh token endpoint nao verifica se user ainda existe/ativo
- SSRF risk no teste de Databricks host (user pode apontar pra 169.254.169.254)
- Sem password complexity validation
- Rate limiter definido mas nunca aplicado

## Solucao
1. Rejeitar webhooks se OMNI_WEBHOOK_SECRET nao configurado
2. Verificar user ativo no refresh token endpoint
3. Validar Databricks host URL contra pattern cloud.databricks.com
4. Adicionar min_length=8 no password field
5. Aplicar rate limiter nos endpoints de auth
6. JWT em httpOnly cookie (futuro — nao blocking)
