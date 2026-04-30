"""Step `storage_configuration` — registra root bucket no Databricks Account.

POST /api/2.0/accounts/{id}/storage-configurations vinculando o S3 root
bucket criado pelo step `s3` ao Databricks Account. Retorna
`storage_configuration_id` que o `workspace_provision` usa pra criar o
workspace customer-managed VPC.

Idempotente via lookup por nome — se ja existe, reutiliza o id.
Roda DEPOIS de `s3` (precisa do root bucket name) e ANTES de
`workspace_provision`.
"""

from __future__ import annotations

import httpx

from app.services.databricks_oauth import account_oauth_token
from app.services.real_saga.base import SagaStepBase, StepContext
from app.services.real_saga.registry import register_saga_step


@register_saga_step("storage_configuration")
class StorageConfigurationStep(SagaStepBase):
    step_id = "storage_configuration"

    async def compensate(self, ctx: StepContext) -> None:
        if not ctx.shared.databricks_storage_config_created:
            return
        env = ctx.env_vars()
        account_id = env.get("databricks_account_id", "")
        oauth_client_id = env.get("databricks_oauth_client_id", "")
        oauth_secret = env.get("databricks_oauth_secret", "")
        config_id = ctx.shared.databricks_storage_config_id
        if not all([account_id, oauth_client_id, oauth_secret, config_id]):
            return

        async def _del() -> None:
            async with httpx.AsyncClient(timeout=30.0) as c:
                token = await account_oauth_token(
                    c, account_id, oauth_client_id, oauth_secret
                )
                await c.delete(
                    f"https://accounts.cloud.databricks.com/api/2.0/accounts/{account_id}/storage-configurations/{config_id}",
                    headers={"Authorization": f"Bearer {token}"},
                )

        await self._safe_compensate(
            ctx, f"storage_config({config_id})", _del, sync=False,
        )

    async def execute(self, ctx: StepContext) -> None:
        env = ctx.env_vars()
        account_id = env.get("databricks_account_id", "")
        oauth_client_id = env.get("databricks_oauth_client_id", "")
        oauth_secret = env.get("databricks_oauth_secret", "")

        if not all([account_id, oauth_client_id, oauth_secret]):
            await ctx.warn(
                "Skipping storage_configuration — Databricks Account OAuth nao "
                "configurado. workspace_provision vai usar databricks_storage_config_id "
                "do env, ou pular se ausente."
            )
            return

        root_bucket = ctx.shared.workspace_root_bucket
        if not root_bucket:
            raise RuntimeError(
                "storage_configuration precisa workspace_root_bucket — "
                "step s3 deve rodar antes e popular ctx.shared.workspace_root_bucket"
            )

        project = env.get("project_name", "medallion-pipeline")
        company_suffix = str(ctx.company_id).split("-")[0]
        config_name = f"{project}-{company_suffix}-storage"

        await ctx.info(
            f"Registrando storage configuration '{config_name}' -> s3://{root_bucket}"
        )

        config_id, was_created = await self._register(
            ctx, account_id, oauth_client_id, oauth_secret,
            config_name, root_bucket,
        )
        ctx.shared.databricks_storage_config_id = config_id
        if was_created:
            ctx.shared.databricks_storage_config_created = True
        await ctx.success(f"Storage configuration: {config_id} (created={was_created})")

    @staticmethod
    async def _register(
        ctx: StepContext,
        account_id: str,
        client_id: str,
        client_secret: str,
        config_name: str,
        root_bucket: str,
    ) -> tuple[str, bool]:
        async with httpx.AsyncClient(timeout=30.0) as c:
            token = await account_oauth_token(
                c, account_id, client_id, client_secret
            )

            list_resp = await c.get(
                f"https://accounts.cloud.databricks.com/api/2.0/accounts/{account_id}/storage-configurations",
                headers={"Authorization": f"Bearer {token}"},
            )
            list_resp.raise_for_status()
            for cfg in list_resp.json() or []:
                if cfg.get("storage_configuration_name") == config_name:
                    await ctx.info(f"Storage config '{config_name}' ja existe — reutilizando")
                    return cfg["storage_configuration_id"], False

            create_resp = await c.post(
                f"https://accounts.cloud.databricks.com/api/2.0/accounts/{account_id}/storage-configurations",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "storage_configuration_name": config_name,
                    "root_bucket_info": {"bucket_name": root_bucket},
                },
            )
            create_resp.raise_for_status()
            return create_resp.json()["storage_configuration_id"], True
