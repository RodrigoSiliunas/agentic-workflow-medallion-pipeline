# Security Deploy Hardening

## Problema
O RealSagaRunner expoe credenciais de multiplas formas:
- Terraform stdout/stderr pode conter secrets e sao persistidos no DB + SSE
- Subprocess recebe ALL env vars do parent process (incluindo secrets de outros tenants)
- WorkspaceClient cached com token plaintext no lru_cache indefinidamente
- Exception messages raw publicados no SSE podem conter infra details

## Solucao
1. Sanitizar terraform output antes de logar (regex para AKIA*, dapi*, ghp_*, sk-ant-*)
2. Construir env minimo pro subprocess (so PATH, HOME, TMP + credenciais necessarias)
3. Remover lru_cache do WorkspaceClient, criar client por saga execution
4. Generalizar exception messages antes de publicar no SSE
