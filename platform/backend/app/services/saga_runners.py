"""Pluggable saga runners — estrategias de execucao das etapas da saga.

A arquitetura separa o orquestrador (que persiste estado, publica eventos SSE,
sequencia os steps) do executor concreto (que faz o trabalho real de cada etapa).

Dois runners disponiveis:

- **MockSagaRunner**: usado nos mocks/demo. Cada step dorme 250-500ms por log
  fake e retorna success sem tocar nada externo.
- **TerraformSagaRunner**: stub que lanca NotImplementedError — esqueleto para
  a implementacao real usando Terraform + Databricks SDK.

A escolha do runner e feita via `settings.SAGA_RUNNER` (env `SAGA_RUNNER`).
Valor default: "mock". Para plugar um runner real:

    SAGA_RUNNER=terraform  # requer credenciais AWS/Databricks configuradas

Um runner customizado basta implementar o protocol `SagaStepRunner` e ser
registrado em `RUNNER_REGISTRY` ou via plugin entry point.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Protocol

import structlog

from app.core.config import settings
from app.models.deployment import Deployment

if TYPE_CHECKING:
    from app.services.real_saga.base import DeploymentCredentials

logger = structlog.get_logger()


# Callback que o runner usa para emitir uma linha de log reativa (persistida +
# publicada no SSE do orquestrador). Assinatura:
#   async def emit_log(level: str, message: str, step_id: str | None = None)
EmitLogFn = Callable[[str, str, str | None], Awaitable[None]]


class SagaStepRunner(Protocol):
    """Contrato pra um runner de etapas da saga.

    O orquestrador (`deployment_saga.run_saga`) chama `execute_step` uma vez
    por step. O runner deve emitir logs via `emit_log` e retornar quando a
    etapa concluir (sucesso) ou levantar exception (falha).

    `credentials` pode ser None (mock runner ignora). O RealSagaRunner
    requer credentials preenchidas — o caller de `run_saga` deve resolver
    override+company antes de disparar.
    """

    async def execute_step(
        self,
        *,
        deployment: Deployment,
        step_id: str,
        step_name: str,
        emit_log: EmitLogFn,
        credentials: DeploymentCredentials | None = None,
    ) -> None: ...


# Logs de exemplo mockados por step (reutilizados pelo MockSagaRunner)
MOCK_STEP_LOGS: dict[str, list[str]] = {
    "validate": [
        "Calling AWS STS GetCallerIdentity...",
        "AWS credentials OK",
        "Validating Databricks token via w.current_user.me()...",
        "Databricks workspace reachable",
        "GitHub PAT has repo scope",
        "Anthropic API key valid (Claude Opus access)",
    ],
    "s3": [
        "Initializing terraform workspace...",
        "terraform init: downloading aws provider 5.x",
        "terraform plan: + aws_s3_bucket.datalake",
        "terraform apply: creating bucket...",
        "Bucket created, enabling versioning + lifecycle rules",
    ],
    "iam": [
        "Creating IAM role databricks-unity-catalog-access...",
        "Attaching policy S3ReadWrite for datalake bucket",
        "Configuring trust relationship with Databricks account",
    ],
    "secrets": [
        "databricks secrets create-scope medallion-pipeline",
        "Uploading aws-access-key-id",
        "Uploading aws-secret-access-key",
        "Uploading anthropic-api-key",
        "Uploading github-token",
        "Uploading masking-secret",
    ],
    "catalog": [
        "CREATE CATALOG IF NOT EXISTS medallion",
        "CREATE SCHEMA medallion.bronze",
        "CREATE SCHEMA medallion.silver",
        "CREATE SCHEMA medallion.gold",
        "CREATE SCHEMA medallion.observer",
        "Grants aplicados ao grupo de usuarios",
    ],
    "upload": [
        "git clone observer-framework branch main",
        "git clone pipeline-seguradora-whatsapp",
        "POST /api/2.0/workspace/import (16 notebooks)",
        "Workspace sync completo",
    ],
    "workflow": [
        "w.jobs.create(name=medallion_pipeline_whatsapp)",
        "Task 1/8: pre_check",
        "Task 2/8: bronze_ingestion",
        "Tasks 3-5/8: silver_* (dedup, entities, enrichment)",
        "Task 6/8: gold_analytics (12 subnotebooks)",
        "Task 7/8: validation",
        "Task 8/8: observer_trigger",
        "Schedule registrado: cron 0 6 * * *",
    ],
    "observer": [
        "Creating workflow observer_agent...",
        "Task 1/1: collect_and_fix (notebook do observer-framework)",
        "Observer pronto para diagnostico automatico",
    ],
    "trigger": [
        "w.jobs.run_now(job_id=job_created)",
        "Run iniciado",
        "Aguardando conclusao...",
        "bronze_ingestion: SUCCESS",
        "silver_*: SUCCESS",
        "gold_analytics: SUCCESS (12 tabelas)",
        "validation: SUCCESS",
        "observer_trigger: EXCLUDED (no failures)",
        "Run completo",
    ],
    "register": [
        "Adicionando pipeline ao dashboard Flowertex",
        "Configurando chat agent para este workflow",
        "Deployment finalizado com sucesso",
    ],
}


class MockSagaRunner:
    """Runner default — simula cada etapa com sleeps e logs fake."""

    name = "mock"

    async def execute_step(
        self,
        *,
        deployment: Deployment,
        step_id: str,
        step_name: str,
        emit_log: EmitLogFn,
        credentials: DeploymentCredentials | None = None,
    ) -> None:
        _ = credentials  # mock ignora — logs fake nao precisam de auth
        # No primeiro step (validate), emite um resumo das credenciais usadas
        # — pro usuario ver que as credenciais do /settings foram picked up,
        # sem precisar digitar tudo de novo no wizard.
        if step_id == "validate":
            await self._emit_credential_sources(deployment, emit_log)

        messages = MOCK_STEP_LOGS.get(step_id, [f"Executing {step_name}..."])
        for msg in messages:
            await asyncio.sleep(0.25 + random.random() * 0.25)
            await emit_log("info", msg, step_id)

    @staticmethod
    async def _emit_credential_sources(
        deployment: Deployment | None, emit_log: EmitLogFn
    ) -> None:
        if deployment is None:
            return
        sources = (deployment.config or {}).get("credential_sources", {})
        if not sources:
            return
        from_company = sorted([t for t, s in sources.items() if s == "company"])
        from_override = sorted([t for t, s in sources.items() if s == "override"])
        missing = sorted([t for t, s in sources.items() if s == "missing"])
        if from_company:
            await emit_log(
                "info",
                f"Credenciais da empresa: {', '.join(from_company)}",
                "validate",
            )
        if from_override:
            await emit_log(
                "info",
                f"Credenciais sobrescritas neste deploy: {', '.join(from_override)}",
                "validate",
            )
        if missing:
            await emit_log(
                "warn",
                f"Credenciais faltando (deploy rodaria em modo degradado): {', '.join(missing)}",
                "validate",
            )


RUNNER_REGISTRY: dict[str, type[SagaStepRunner]] = {
    "mock": MockSagaRunner,
    # "real" e resolvido lazy dentro de `get_runner()` pra evitar ciclos de
    # import — real_saga depende de Deployment model, que depende de Base.
}


def get_runner() -> SagaStepRunner:
    """Devolve o runner configurado via `settings.SAGA_RUNNER`.

    Cai no mock com aviso se o nome nao existir.
    """
    name = settings.SAGA_RUNNER.lower()

    if name == "real":
        # Lazy import pra evitar ciclo: real_saga importa Deployment model
        # que pode importar services que referenciam este modulo.
        from app.services.real_saga import RealSagaRunner

        return RealSagaRunner()

    runner_cls = RUNNER_REGISTRY.get(name)
    if not runner_cls:
        logger.warning("saga runner desconhecido, usando mock", requested=name)
        runner_cls = MockSagaRunner
    return runner_cls()
