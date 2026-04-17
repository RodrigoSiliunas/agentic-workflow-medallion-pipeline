"""Step `secrets` — cria/atualiza o Databricks secret scope `medallion-pipeline`.

Cria o scope se nao existir e poe cada credencial como um secret individual.
Idempotente: `put_secret` com overwrite implicito.
"""

from __future__ import annotations

import asyncio
import contextlib

from databricks.sdk.errors import ResourceAlreadyExists
from databricks.sdk.service.workspace import ScopeBackendType

from app.services.real_saga.base import StepContext
from app.services.real_saga.databricks_client import workspace_client
from app.services.real_saga.registry import register_saga_step

_SECRETS_FROM_CREDENTIALS: dict[str, str] = {
    # databricks secret key -> attribute no DeploymentCredentials
    "aws-access-key-id": "aws_access_key_id",
    "aws-secret-access-key": "aws_secret_access_key",
    "aws-region": "aws_region",
    "anthropic-api-key": "anthropic_api_key",
    "github-token": "github_token",
    "github-repo": "github_repo",
}

# Secret key que vem de env_vars (nao de credentials)
_SECRETS_FROM_ENV_VARS: dict[str, str] = {
    "masking-secret": "masking_secret",
    "s3-bucket": "s3_bucket",
}


@register_saga_step("secrets")
class SecretsStep:
    step_id = "secrets"

    async def execute(self, ctx: StepContext) -> None:
        scope_name = ctx.env_vars().get("secret_scope", "medallion-pipeline")
        w = workspace_client(ctx.credentials)

        await ctx.info(f"Garantindo secret scope '{scope_name}' no workspace")

        def _ensure_scope() -> None:
            with contextlib.suppress(ResourceAlreadyExists):
                w.secrets.create_scope(
                    scope=scope_name,
                    scope_backend_type=ScopeBackendType.DATABRICKS,
                )

        await asyncio.to_thread(_ensure_scope)
        await ctx.info("Scope ok — enviando secrets")

        env_vars = ctx.env_vars()
        emitted = 0
        missing: list[str] = []
        for secret_key, attr in _SECRETS_FROM_CREDENTIALS.items():
            value = getattr(ctx.credentials, attr, None)
            if not value:
                missing.append(secret_key)
                continue
            await asyncio.to_thread(
                lambda k=secret_key, v=value: w.secrets.put_secret(
                    scope=scope_name, key=k, string_value=v
                )
            )
            emitted += 1
            await ctx.info(f"  put secret: {secret_key}")

        for secret_key, env_key in _SECRETS_FROM_ENV_VARS.items():
            value = env_vars.get(env_key)
            if not value:
                missing.append(secret_key)
                continue
            await asyncio.to_thread(
                lambda k=secret_key, v=value: w.secrets.put_secret(
                    scope=scope_name, key=k, string_value=v
                )
            )
            emitted += 1
            await ctx.info(f"  put secret: {secret_key}")

        if missing:
            await ctx.warn(f"Secrets nao enviados (sem valor): {', '.join(missing)}")
        await ctx.success(f"{emitted} secrets ativos no scope '{scope_name}'")
        ctx.shared.secret_scope = scope_name
