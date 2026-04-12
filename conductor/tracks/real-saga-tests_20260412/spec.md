# Real Saga Tests

## Problema
15 arquivos do real_saga/ (runner + clients + 10 steps) com ZERO testes unitarios.
CredentialService sem testes. Frontend sem nenhum test file apesar de Vitest configurado.
Sem factories/fixtures compartilhados pra facilitar test authoring.

## Solucao
1. Criar test factories (make_deployment, make_credentials, make_step_context)
2. Unit tests pro TerraformRunner (mock subprocess)
3. Unit tests pros steps mais criticos (validate, s3, workflow, trigger)
4. Unit tests pro CredentialService (encrypt/decrypt round-trip, type validation)
5. Integration test do saga completo (mock runner, verify DB state)
6. Frontend: test do auth store (JWT decode, expiration, mock mode)
