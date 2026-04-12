"""Tipos compartilhados pelos steps do RealSagaRunner."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from app.models.deployment import Deployment

EmitLogFn = Callable[[str, str, str | None], Awaitable[None]]


@dataclass
class DeploymentCredentials:
    """Credenciais resolvidas (override > company) passadas pro step executar deploy real.

    Todos os campos sao plaintext ja decriptados. Nunca persistir em DB — viver
    apenas na memoria pelo tempo de vida da saga.
    """

    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_region: str | None = None
    databricks_host: str | None = None
    databricks_token: str | None = None
    github_token: str | None = None
    github_repo: str | None = None
    anthropic_api_key: str | None = None

    def require(self, field_name: str) -> str:
        value = getattr(self, field_name, None)
        if not value:
            raise CredentialMissingError(
                f"Credencial obrigatoria nao configurada: {field_name}"
            )
        return value

    def to_env(self) -> dict[str, str]:
        """Exporta credenciais como dict de env vars — util pra subprocess."""
        env: dict[str, str] = {}
        if self.aws_access_key_id:
            env["AWS_ACCESS_KEY_ID"] = self.aws_access_key_id
        if self.aws_secret_access_key:
            env["AWS_SECRET_ACCESS_KEY"] = self.aws_secret_access_key
        if self.aws_region:
            env["AWS_REGION"] = self.aws_region
            env["AWS_DEFAULT_REGION"] = self.aws_region
        if self.databricks_host:
            env["DATABRICKS_HOST"] = self.databricks_host
        if self.databricks_token:
            env["DATABRICKS_TOKEN"] = self.databricks_token
        if self.github_token:
            env["GITHUB_TOKEN"] = self.github_token
        if self.github_repo:
            env["GITHUB_REPO"] = self.github_repo
        if self.anthropic_api_key:
            env["ANTHROPIC_API_KEY"] = self.anthropic_api_key
        return env


class CredentialMissingError(Exception):
    """Credencial obrigatoria nao encontrada no contexto."""


@dataclass
class SharedSagaState:
    """Estado compartilhado entre steps do mesmo deploy — tipado pra eliminar
    isinstance guards e stringly-typed keys nos steps."""

    s3_bucket: str | None = None
    s3_bucket_url: str | None = None
    databricks_role_arn: str | None = None
    secret_scope: str | None = None
    catalog: str | None = None
    repo_path: str | None = None
    observer_job_id: int | None = None
    workflow_job_id: int | None = None
    run_id: int | None = None


@dataclass
class StepContext:
    """Contexto passado pra cada step durante a execucao do deploy real."""

    deployment: Deployment
    step_id: str
    step_name: str
    credentials: DeploymentCredentials
    emit_log: EmitLogFn
    # Diretorio de trabalho por-company pro state do terraform + arquivos temp
    state_dir: Path
    # Resultados compartilhados entre steps — tipado pra type safety.
    shared: SharedSagaState = field(default_factory=SharedSagaState)

    @property
    def deployment_id(self) -> uuid.UUID:
        return self.deployment.id

    @property
    def company_id(self) -> uuid.UUID:
        return self.deployment.company_id

    def env_vars(self) -> dict[str, str]:
        """Env vars do template (catalog name, schedule cron, masking secret, etc)."""
        return (self.deployment.config or {}).get("env_vars", {}) or {}

    async def info(self, message: str) -> None:
        await self.emit_log("info", message, self.step_id)

    async def warn(self, message: str) -> None:
        await self.emit_log("warn", message, self.step_id)

    async def error(self, message: str) -> None:
        await self.emit_log("error", message, self.step_id)

    async def success(self, message: str) -> None:
        await self.emit_log("success", message, self.step_id)


class SagaStep(Protocol):
    """Contrato de um step do RealSagaRunner."""

    step_id: str

    async def execute(self, ctx: StepContext) -> None: ...
