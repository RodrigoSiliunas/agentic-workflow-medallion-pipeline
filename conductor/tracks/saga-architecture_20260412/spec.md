# Saga Architecture Cleanup

## Problema
- run_saga() é monolito de 260 linhas com 5+ responsabilidades
- Shared state entre steps usa dict[str, object] sem type safety
- SAGA_BLUEPRINT duplicado em 3 lugares (backend, frontend, mock logs)
- Memory leak em _shared_per_deployment quando saga falha
- RegisterStep é no-op — Pipeline creation hardcoded no orchestrator

## Solucao
1. Criar dataclass SharedSagaState tipado com campos para cada output compartilhado
2. Expor SAGA_BLUEPRINT via API endpoint (single source of truth)
3. Mover Pipeline creation pro RegisterStep (step recebe DB session via context)
4. Cleanup do shared state no finally block do orchestrator
5. Extrair SagaEventEmitter do run_saga pra reduzir tamanho
