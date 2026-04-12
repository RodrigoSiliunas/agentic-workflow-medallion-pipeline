# Plan: Pluggable Saga Runner

## Tasks

- [x] `services/saga_runners.py` com Protocol + MockSagaRunner + TerraformSagaRunner + get_runner factory
- [x] `MOCK_STEP_LOGS` movido pra la (re-exportado de `deployment_saga.py` pra compat)
- [x] `run_saga()` refatorado: loop chama `runner.execute_step` + helper `emit_log` inline
- [x] `config.py`: `SAGA_RUNNER: str = "mock"`
- [x] `.env.example`: flag documentada
- [x] `tests/unit/test_saga_runners.py` (6 tests)
- [x] Full suite 49 passing
