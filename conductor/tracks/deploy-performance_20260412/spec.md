# Deploy Performance Optimization

## Problema
- N+1 commits no emit_log (~100 db.commit() por deploy)
- Credential resolution: 8 queries sequenciais no POST /deployments
- Validate step: 4 checks sequenciais (docstring diz "paralelo")
- Secrets step: 7 put_secret sequenciais
- Catalog step: 7 DDL sequenciais
- SSE queue drops events silenciosamente
- Upload step: linear scan de todos os repos

## Solucao
1. Batch commits: flush sem commit, commit no fim de cada step
2. get_all_decrypted() bulk query pra credentials
3. asyncio.gather nos validate, secrets, e catalog steps
4. SSE queue com drop-oldest strategy + garantia de terminal events
5. Upload: usar path_prefix filter na Repos API
