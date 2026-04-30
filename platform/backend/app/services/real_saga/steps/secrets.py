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

    async def compensate(self, ctx: StepContext) -> None:
        """Rollback: deleta secret scope SE foi criado nesta saga.

        Skip se adopted (existia antes — outros pipelines podem usar).
        """
        if not ctx.shared.databricks_secret_scope_created:
            await ctx.info("compensate(secrets): scope nao foi criado nesta saga — skip")
            return
        scope = ctx.shared.secret_scope
        if not scope:
            return
        w = workspace_client(ctx.credentials)
        try:
            await asyncio.to_thread(lambda: w.secrets.delete_scope(scope=scope))
            await ctx.info(f"compensate(secrets): scope {scope} removido")
        except Exception as exc:  # noqa: BLE001
            await ctx.warn(f"compensate(secrets) falhou: {exc}")

    async def execute(self, ctx: StepContext) -> None:
        scope_name = ctx.env_vars().get("secret_scope", "medallion-pipeline")
        w = workspace_client(ctx.credentials)

        await ctx.info(f"Garantindo secret scope '{scope_name}' no workspace")

        def _scope_exists() -> bool:
            return any(s.name == scope_name for s in w.secrets.list_scopes())

        scope_pre_exists = await asyncio.to_thread(_scope_exists)

        def _ensure_scope() -> None:
            with contextlib.suppress(ResourceAlreadyExists):
                w.secrets.create_scope(
                    scope=scope_name,
                    scope_backend_type=ScopeBackendType.DATABRICKS,
                )

        await asyncio.to_thread(_ensure_scope)
        if not scope_pre_exists:
            ctx.shared.databricks_secret_scope_created = True
        await ctx.info("Scope ok — enviando secrets em paralelo")

        # Coleta secrets a enviar — cada um vira uma task assincrona disparada
        # via asyncio.gather. Antes era serial: 8 secrets x ~300ms = 2.4s.
        # Paralelizado: ~300ms total (limitado pelo slowest put_secret).
        env_vars = ctx.env_vars()
        to_put: list[tuple[str, str]] = []
        missing: list[str] = []

        for secret_key, attr in _SECRETS_FROM_CREDENTIALS.items():
            value = getattr(ctx.credentials, attr, None)
            if value:
                to_put.append((secret_key, value))
            else:
                missing.append(secret_key)

        for secret_key, env_key in _SECRETS_FROM_ENV_VARS.items():
            value = env_vars.get(env_key)
            if value:
                to_put.append((secret_key, value))
            else:
                missing.append(secret_key)

        async def _put(key: str, val: str) -> str:
            await asyncio.to_thread(
                lambda: w.secrets.put_secret(
                    scope=scope_name, key=key, string_value=val
                )
            )
            return key

        emitted_keys = await asyncio.gather(*(_put(k, v) for k, v in to_put))
        for k in emitted_keys:
            await ctx.info(f"  put secret: {k}")

        if missing:
            await ctx.warn(f"Secrets nao enviados (sem valor): {', '.join(missing)}")
        await ctx.success(f"{len(emitted_keys)} secrets ativos no scope '{scope_name}'")
        ctx.shared.secret_scope = scope_name
