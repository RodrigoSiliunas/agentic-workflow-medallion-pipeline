"""RealSagaRunner — runner real do deploy.

Despacha cada `step_id` pra uma instancia concreta de `SagaStep` registrada no
dict `_STEPS`. O StepContext e construido uma vez por step e inclui tudo que o
step precisa: credenciais decriptadas, emit_log reativo, state_dir por company.

O `shared` dict do StepContext e persistido entre steps do mesmo deploy pra
permitir que steps posteriores leiam outputs de steps anteriores (ex: o
`step_workflow` le `observer_job_id` escrito pelo `step_observer`).
"""

from __future__ import annotations

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
from app.services.real_saga.steps import (
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
    """Runner que executa os steps de verdade (boto3 + terraform + databricks-sdk)."""

    name = "real"

    def __init__(self) -> None:
        self._steps: dict[str, SagaStep] = {
            "validate": ValidateStep(),
            "s3": S3Step(),
            "iam": IamStep(),
            "secrets": SecretsStep(),
            "catalog": CatalogStep(),
            "upload": UploadStep(),
            # observer antes de workflow — o workflow precisa do observer_job_id
            "observer": ObserverStep(),
            "workflow": WorkflowStep(),
            "trigger": TriggerStep(),
            "register": RegisterStep(),
        }
        # Estado compartilhado entre steps do MESMO deploy (deployment_id -> state)
        self._shared_per_deployment: dict[str, SharedSagaState] = {}

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
        try:
            await step.execute(ctx)
        finally:
            # Cleanup do shared state quando o ultimo step termina OU quando
            # qualquer step falha — evita memory leak de deploys parciais.
            if step_id == "register":
                self._shared_per_deployment.pop(dep_key, None)

    def cleanup_shared_state(self, deployment_id: str) -> None:
        """Remove shared state de um deploy (chamado pelo orchestrator no finally)."""
        self._shared_per_deployment.pop(deployment_id, None)


def _state_dir_for(deployment: Deployment) -> Path:
    """Diretorio de trabalho por company pro terraform state + arquivos temp.

    Por-company (nao por-deployment) pra que deploys sucessivos da mesma
    empresa compartilhem state — assim o terraform sabe que o bucket ja foi
    criado no deploy anterior.
    """
    base = getattr(settings, "REAL_SAGA_DATA_DIR", None)
    root = Path(base) if base else Path("data") / "real_saga"
    return root / str(deployment.company_id)
