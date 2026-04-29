"""Step `metastore_assign` — attacha workspace ao Unity Catalog metastore.

PUT /api/2.0/accounts/{id}/metastores/{metastore_id}/workspaces/{workspace_id}
liga o workspace recem-criado pelo `workspace_provision` ao metastore regional
do Databricks Account. Sem isso, qualquer operacao Unity Catalog (catalog,
schema, table) falha com METASTORE_NOT_ASSIGNED.

Idempotente:
- Se workspace ja attached ao metastore correto, no-op
- Se attached a OUTRO metastore, raise (intervencao manual necessaria)

Roda APOS workspace_provision e ANTES de catalog. metastore_id vem de:
1. ctx.shared.databricks_metastore_id (preenchido por step anterior se existir)
2. env_vars["databricks_metastore_id"] (input do advanced ou default da regiao)
3. Lookup automatico via Account API (primeiro metastore da regiao)
"""

from __future__ import annotations

import httpx

from app.services.real_saga.base import SagaStepBase, StepContext
from app.services.real_saga.registry import register_saga_step


@register_saga_step("metastore_assign")
class MetastoreAssignStep(SagaStepBase):
    step_id = "metastore_assign"

    async def compensate(self, ctx: StepContext) -> None:
        """No-op: detach do metastore orfa o catalog + dados subjacentes.

        Workspace sera deletado pelo workspace_provision.compensate de
        qualquer forma (delete cascata o detach automatico Account-side).
        """
        await ctx.info(
            "compensate(metastore_assign): no-op (detach risca data loss)"
        )

    async def execute(self, ctx: StepContext) -> None:
        env = ctx.env_vars()
        account_id = env.get("databricks_account_id", "")
        oauth_client_id = env.get("databricks_oauth_client_id", "")
        oauth_secret = env.get("databricks_oauth_secret", "")

        if not all([account_id, oauth_client_id, oauth_secret]):
            await ctx.warn("Skipping metastore_assign — Account OAuth ausente")
            return

        workspace_id = ctx.shared.databricks_workspace_id
        if not workspace_id:
            raise RuntimeError(
                "metastore_assign precisa databricks_workspace_id — "
                "step workspace_provision deve rodar antes"
            )

        region = ctx.credentials.require("aws_region")

        async with httpx.AsyncClient(timeout=60.0) as c:
            token = await self._get_token(c, account_id, oauth_client_id, oauth_secret)

            metastore_id = (
                ctx.shared.databricks_metastore_id
                or env.get("databricks_metastore_id", "")
                or await self._discover_metastore(ctx, c, account_id, token, region)
            )

            if not metastore_id:
                raise RuntimeError(
                    f"Nenhum metastore encontrado em {region}. Crie um via "
                    "Account Console > Data > Metastores ou passe "
                    "databricks_metastore_id no advanced."
                )

            await ctx.info(
                f"Verificando attachment workspace={workspace_id} -> metastore={metastore_id}"
            )

            # Check current assignment
            current_resp = await c.get(
                f"https://accounts.cloud.databricks.com/api/2.0/accounts/{account_id}/workspaces/{workspace_id}/metastore",
                headers={"Authorization": f"Bearer {token}"},
            )
            if current_resp.status_code == 200:
                current = current_resp.json().get("metastore_id")
                if current == metastore_id:
                    await ctx.info("Workspace ja attached ao metastore correto")
                    ctx.shared.databricks_metastore_id = metastore_id
                    return
                if current:
                    raise RuntimeError(
                        f"Workspace ja attached a OUTRO metastore ({current}). "
                        "Detach manual via Account Console antes de re-rodar."
                    )

            # Attach
            put_resp = await c.put(
                f"https://accounts.cloud.databricks.com/api/2.0/accounts/{account_id}/workspaces/{workspace_id}/metastore",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "metastore_id": metastore_id,
                    "default_catalog_name": env.get("catalog", "medallion"),
                },
            )
            put_resp.raise_for_status()
            ctx.shared.databricks_metastore_id = metastore_id
            ctx.shared.databricks_metastore_assigned = True
            await ctx.success(
                f"Workspace {workspace_id} attached ao metastore {metastore_id}"
            )

    @staticmethod
    async def _get_token(
        c: httpx.AsyncClient, account_id: str, client_id: str, secret: str
    ) -> str:
        resp = await c.post(
            f"https://accounts.cloud.databricks.com/oidc/accounts/{account_id}/v1/token",
            auth=(client_id, secret),
            data={"grant_type": "client_credentials", "scope": "all-apis"},
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    @staticmethod
    async def _discover_metastore(
        ctx: StepContext,
        c: httpx.AsyncClient,
        account_id: str,
        token: str,
        region: str,
    ) -> str | None:
        """Acha o primeiro metastore que match a regiao do deploy.

        Metastores sao Account-scope mas regionais — workspace so pode
        attachar metastore da mesma regiao AWS.
        """
        list_resp = await c.get(
            f"https://accounts.cloud.databricks.com/api/2.0/accounts/{account_id}/metastores",
            headers={"Authorization": f"Bearer {token}"},
        )
        list_resp.raise_for_status()
        metastores = list_resp.json().get("metastores", []) or []
        for m in metastores:
            if m.get("region") == region:
                mid = m.get("metastore_id")
                await ctx.info(
                    f"Metastore auto-discover: {m.get('name')} ({mid}) em {region}"
                )
                return mid
        await ctx.warn(f"Nenhum metastore em {region} dentre {len(metastores)} listados")
        return None
