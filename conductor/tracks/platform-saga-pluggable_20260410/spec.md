# Specification: Pluggable Saga Runner

**Track ID:** platform-saga-pluggable_20260410
**Status:** Complete

## Summary

Separa o orquestrador da saga (persistencia + pub/sub SSE + sequenciamento) do executor concreto (o que faz cada step). O runner e configuravel via `SAGA_RUNNER` env e permite plugar um backend real (Terraform + Databricks SDK) sem tocar no orquestrador.

## Arquitetura

```
run_saga(deployment_id, runner=None)
  ├── runner = runner or get_runner()  # factory via settings.SAGA_RUNNER
  ├── inicializa steps no DB
  ├── for blueprint in SAGA_BLUEPRINT:
  │     step.status = running
  │     runner.execute_step(deployment, step_id, step_name, emit_log)
  │     step.status = success
  ├── cria Pipeline no DB (track G)
  └── status = success
```

A interface `SagaStepRunner` e um `typing.Protocol` com um unico metodo:

```python
async def execute_step(
    *,
    deployment: Deployment,
    step_id: str,
    step_name: str,
    emit_log: EmitLogFn,
) -> None: ...
```

## Runners disponiveis

- **MockSagaRunner** (default): `sleep(0.25-0.5) + emit_log(info, msg)` por mensagem fake em `MOCK_STEP_LOGS[step_id]`
- **TerraformSagaRunner**: stub que `emit_log(warn, ...)` + `raise NotImplementedError`. Docstring detalha 10 acoes reais a implementar por step

## Factory

```python
# app/services/saga_runners.py
RUNNER_REGISTRY = {"mock": MockSagaRunner, "terraform": TerraformSagaRunner}

def get_runner() -> SagaStepRunner:
    name = settings.SAGA_RUNNER.lower()
    return RUNNER_REGISTRY.get(name, MockSagaRunner)()
```

Fallback gracioso para mock se nome invalido + warning no log.

## Config

- `app/core/config.py`: `SAGA_RUNNER: str = "mock"`
- `.env.example`: documentado com exemplo e warning sobre `terraform` ainda ser stub

## Tests

- `tests/unit/test_saga_runners.py` com 6 tests:
  - registry tem ambos
  - get_runner default mock
  - get_runner terraform
  - fallback para mock em nome invalido
  - mock emite N logs (N = len(MOCK_STEP_LOGS[step_id]))
  - terraform raise NotImplementedError + warn antes

## Impacto no orquestrador

- `run_saga()` aceita `runner: SagaStepRunner | None = None` (injetavel pra testes)
- Funcao interna `emit_log(level, message, step_id)` criada dentro do loop per-step
- `NotImplementedError` do runner → step.status = failed + re-raise

## Para plugar um runner real

1. Implementar classe com `async def execute_step(self, *, ...)`
2. Registrar em `RUNNER_REGISTRY["meu-runner"] = MinhaClasse`
3. Setar `SAGA_RUNNER=meu-runner`

Ou injetar direto: `await run_saga(deployment_id, runner=MeuRunner())`
