# Plan: Saga Architecture Cleanup

## Phase 1: Typed shared state
- [ ] Task 1: Criar SharedSagaState dataclass em base.py com campos tipados
- [ ] Task 2: Substituir dict[str, object] por SharedSagaState em StepContext
- [ ] Task 3: Atualizar todos os steps pra usar campos tipados (sem isinstance guards)

## Phase 2: Blueprint single source of truth
- [ ] Task 4: Criar GET /api/v1/deployments/blueprint endpoint no backend
- [ ] Task 5: Frontend consome blueprint da API ao inves de hardcodar

## Phase 3: Orchestrator cleanup
- [ ] Task 6: Extrair SagaEventEmitter class do run_saga
- [ ] Task 7: Mover Pipeline creation pro RegisterStep
- [ ] Task 8: Cleanup shared state no finally block do orchestrator
