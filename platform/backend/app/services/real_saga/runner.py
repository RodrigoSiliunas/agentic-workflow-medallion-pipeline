"""RealSagaRunner — runner real do deploy.

Despacha cada `step_id` pra uma instancia concreta de `SagaStep` registrada no
dict `_STEPS`. O StepContext e construido uma vez por step e inclui tudo que o
step precisa: credenciais decriptadas, emit_log reativo, state_dir por company.

O `shared` dict do StepContext e persistido entre steps do mesmo deploy pra
permitir que steps posteriores leiam outputs de steps anteriores (ex: o
`step_workflow` le `observer_job_id` escrito pelo `step_observer`).
"""

from __future__ import annotations

import contextlib
from pathlib import Path

import structlog

from app.core.config import settings
from app.models.deployment import Deployment
from app.services.real_saga.base import (
    DeploymentCredentials,
    EmitLogFn,
    SagaStep,
    SharedSagaState,
    StepContext,
)
from app.services.real_saga.registry import STEP_REGISTRY
from app.services.real_saga.steps import (  # noqa: F401 — import pra popular o registry
    CatalogStep,
    IamStep,
    ObserverStep,
    RegisterStep,
    S3Step,
    SecretsStep,
    TriggerStep,
    UploadStep,
    ValidateStep,
    WorkflowStep,
)

logger = structlog.get_logger()


class RealSagaRunner:
    """Runner que executa os steps de verdade (boto3 + terraform + databricks-sdk).

    T4 hardening:
    - Track completed_steps por deployment pra habilitar compensate em reverse
    - `run_compensation(deployment_id)` percorre completados em ordem inversa
    - cleanup_shared_state chamado pelo orchestrator no finally
    """

    name = "real"

    def __init__(self) -> None:
        # T4 Phase 4: instancia steps a partir do STEP_REGISTRY populado
        # pelos decorators `@register_saga_step`. Adicionar step novo =
        # escrever a classe + import em steps/__init__.py. Runner nao precisa
        # mais editar a cada novo step.
        self._steps: dict[str, SagaStep] = {
            step_id: cls() for step_id, cls in STEP_REGISTRY.items()
        }
        # Estado compartilhado entre steps do MESMO deploy (deployment_id -> state)
        self._shared_per_deployment: dict[str, SharedSagaState] = {}
        # Historico de steps completados com sucesso, em ordem — usado pra
        # percorrer compensate em reverse quando um step posterior falha.
        self._completed_per_deployment: dict[str, list[tuple[str, StepContext]]] = {}

    async def execute_step(
        self,
        *,
        deployment: Deployment,
        step_id: str,
        step_name: str,
        emit_log: EmitLogFn,
        credentials: DeploymentCredentials | None = None,
    ) -> None:
        step = self._steps.get(step_id)
        if step is None:
            raise ValueError(f"step_id desconhecido: {step_id}")

        if credentials is None:
            raise ValueError(
                "RealSagaRunner.execute_step precisa receber credentials — "
                "o orquestrador deve passar via kwargs."
            )

        dep_key = str(deployment.id)
        shared = self._shared_per_deployment.setdefault(dep_key, SharedSagaState())
        completed = self._completed_per_deployment.setdefault(dep_key, [])

        state_dir = _state_dir_for(deployment)
        state_dir.mkdir(parents=True, exist_ok=True)

        ctx = StepContext(
            deployment=deployment,
            step_id=step_id,
            step_name=step_name,
            credentials=credentials,
            emit_log=emit_log,
            state_dir=state_dir,
            shared=shared,
        )

        logger.info(
            "real saga step starting",
            deployment_id=dep_key,
            step_id=step_id,
        )
        await step.execute(ctx)
        # Registra APOS success — falha nao entra no historico.
        completed.append((step_id, ctx))

    async def run_compensation(
        self,
        deployment_id: str,
        emit_log: EmitLogFn | None = None,
    ) -> None:
        """Dispara compensate dos steps completados em ordem reversa.

        Chamado pelo orquestrador quando qualquer step falha. Cada
        compensate deve tolerar "recurso ja deletado" sem raise — loga
        warn e continua. Uma excecao dentro de compensate NAO aborta o
        restante da cadeia (perderia rollback dos outros recursos).
        """
        completed = self._completed_per_deployment.get(deployment_id, [])
        if not completed:
            return

        logger.info(
            "starting saga compensation",
            deployment_id=deployment_id,
            completed_count=len(completed),
        )

        for step_id, ctx in reversed(completed):
            step = self._steps.get(step_id)
            if step is None:
                continue
            compensate = getattr(step, "compensate", None)
            if not callable(compensate):
                # Step legacy sem compensate — registra skip. Ainda nao
                # migramos todos os steps pra SagaStepBase.
                logger.debug(
                    "compensate skip — step sem metodo",
                    deployment_id=deployment_id,
                    step_id=step_id,
                )
                continue
            try:
                await compensate(ctx)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "compensate step raised — continuing rollback",
                    deployment_id=deployment_id,
                    step_id=step_id,
                    error=str(exc),
                )
                if emit_log is not None:
                    with contextlib.suppress(Exception):
                        await emit_log(
                            "warn",
                            f"compensate({step_id}) falhou: {exc}",
                            step_id,
                        )

    def cleanup_shared_state(self, deployment_id: str) -> None:
        """Remove shared state + completed history de um deploy.

        Chamado pelo orchestrator no finally — libera memoria mesmo quando
        o deploy falha ou e cancelado.
        """
        self._shared_per_deployment.pop(deployment_id, None)
        self._completed_per_deployment.pop(deployment_id, None)


def _state_dir_for(deployment: Deployment) -> Path:
    """Diretorio de trabalho por company pro terraform state + arquivos temp.

    Por-company (nao por-deployment) pra que deploys sucessivos da mesma
    empresa compartilhem state — assim o terraform sabe que o bucket ja foi
    criado no deploy anterior.
    """
    base = getattr(settings, "REAL_SAGA_DATA_DIR", None)
    root = Path(base) if base else Path("data") / "real_saga"
    return root / str(deployment.company_id)
