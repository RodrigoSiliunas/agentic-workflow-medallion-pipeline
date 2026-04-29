"""Step `workspace_provision` — cria workspace Databricks via Account API.

Terceiro step novo da saga completa. Cria workspace apontando pra
network_id + credentials_id + storage_configuration_id dos steps anteriores.

Fluxo (workspace_mode=new ou ausente):
1. POST /api/2.0/accounts/{id}/workspaces (201 PROVISIONING)
2. Polling ate workspace_status=RUNNING (max 10min)
3. SCIM: add admin user + put em admins group
4. Gera PAT via OAuth bearer token
5. Retorna workspace_host + pat em shared state

Fluxo (workspace_mode=existing):
1. GET workspace por id, hidrata ctx.shared (network_id, credentials_id, etc)
2. Pula creation flow inteiro
3. Tenta gerar PAT novo via OAuth ou usa o que veio do wizard

Requer (modo new): network_id, credentials_id, storage_configuration_id
ja criados pelos steps anteriores. Nome customizado via env_vars["workspace_name"]
ou derivado do company_id.
Requer (modo existing): env_vars["workspace_id"] do workspace alvo.
"""

from __future__ import annotations

import asyncio

import httpx

from app.services.real_saga.base import SagaStepBase, StepContext
from app.services.real_saga.registry import register_saga_step


@register_saga_step("workspace_provision")
class WorkspaceProvisionStep(SagaStepBase):
    step_id = "workspace_provision"

    async def compensate(self, ctx: StepContext) -> None:
        """Rollback: delete workspace se foi CRIADO nesta saga.

        Skip se workspace_mode=existing (nunca deve deletar workspace adotado).
        """
        env = ctx.env_vars()
        if env.get("workspace_mode") == "existing":
            return
        if not ctx.shared.databricks_workspace_created:
            return
        ws_id = ctx.shared.databricks_workspace_id
        if not ws_id:
            return

        account_id = env.get("databricks_account_id", "")
        client_id = env.get("databricks_oauth_client_id", "")
        secret = env.get("databricks_oauth_secret", "")
        if not all([account_id, client_id, secret]):
            return

        async def _del() -> None:
            async with httpx.AsyncClient(timeout=120.0) as c:
                tok = await c.post(
                    f"https://accounts.cloud.databricks.com/oidc/accounts/{account_id}/v1/token",
                    auth=(client_id, secret),
                    data={"grant_type": "client_credentials", "scope": "all-apis"},
                )
                tok.raise_for_status()
                token = tok.json()["access_token"]
                await c.delete(
                    f"https://accounts.cloud.databricks.com/api/2.0/accounts/{account_id}/workspaces/{ws_id}",
                    headers={"Authorization": f"Bearer {token}"},
                )

        await self._safe_compensate(ctx, f"workspace({ws_id})", _del, sync=False)

    async def execute(self, ctx: StepContext) -> None:
        env = ctx.env_vars()
        account_id = env.get("databricks_account_id", "")
        oauth_client_id = env.get("databricks_oauth_client_id", "")
        oauth_secret = env.get("databricks_oauth_secret", "")
        # storage_config_id: precedencia shared (step storage_configuration) > env legado
        storage_config_id = (
            ctx.shared.databricks_storage_config_id
            or env.get("databricks_storage_config_id", "")
        )

        network_id = ctx.shared.databricks_network_id
        credentials_id = ctx.shared.databricks_credentials_id

        # Modo existing: pega config completa do workspace ja existente
        # via Account API, popula shared state. Depois disso skip todo
        # o resto (creation flow).
        if env.get("workspace_mode") == "existing":
            ws_id = env.get("workspace_id", "")
            if not ws_id:
                raise RuntimeError(
                    "workspace_mode=existing exige workspace_id no env_vars"
                )
            # Fallback sem OAuth: usuario digitou workspace_id + host manualmente
            # no wizard. Pula introspect Account API, hidrata shared state com
            # o que tiver. Steps subsequentes (catalog/cluster/upload) usam PAT
            # workspace-level direto.
            if not all([account_id, oauth_client_id, oauth_secret]):
                workspace_host = ctx.credentials.databricks_host or ""
                if not workspace_host:
                    raise RuntimeError(
                        "workspace_mode=existing sem OAuth M2M precisa "
                        "databricks_host nas credentials (digite manualmente "
                        "no wizard ou configure em /settings)"
                    )
                if not ctx.credentials.databricks_token:
                    raise RuntimeError(
                        "workspace_mode=existing sem OAuth precisa de PAT "
                        "(databricks_token) nas credentials"
                    )
                ctx.shared.databricks_workspace_id = int(ws_id)
                ctx.shared.databricks_workspace_host = workspace_host
                await ctx.success(
                    f"Workspace existente adotado (modo manual): {workspace_host}"
                )
                return
            await self._adopt_existing_workspace(
                ctx, account_id, oauth_client_id, oauth_secret, ws_id,
            )
            return

        if not all([account_id, oauth_client_id, oauth_secret, storage_config_id]):
            await ctx.warn(
                "Skipping workspace_provision — Account API config OU "
                "storage_config_id ausente. Rode storage_configuration antes."
            )
            return
        if not network_id or not credentials_id:
            raise RuntimeError(
                "workspace_provision precisa network_id + credentials_id — "
                "steps network e workspace_credential devem rodar antes"
            )

        project = env.get("project_name", "medallion-pipeline")
        # Nome customizado do advanced > derivado company_id
        custom_name = (env.get("workspace_name") or "").strip()
        if custom_name:
            workspace_name = custom_name
        else:
            company_suffix = str(ctx.company_id).split("-")[0]
            workspace_name = f"{project}-{company_suffix}"
        region = ctx.credentials.require("aws_region")
        admin_email = env.get("admin_email", "administrator@idlehub.com.br")

        await ctx.info(f"Criando workspace '{workspace_name}' em {region}")

        async with httpx.AsyncClient(timeout=600.0) as c:
            token = await self._get_oauth_token(c, account_id, oauth_client_id, oauth_secret)

            # Check existing
            workspaces_resp = await c.get(
                f"https://accounts.cloud.databricks.com/api/2.0/accounts/{account_id}/workspaces",
                headers={"Authorization": f"Bearer {token}"},
            )
            workspaces_resp.raise_for_status()
            existing = next(
                (w for w in workspaces_resp.json() or []
                 if w.get("workspace_name") == workspace_name),
                None,
            )

            if existing and existing.get("workspace_status") == "RUNNING":
                workspace = existing
                await ctx.info(f"Workspace {workspace_name} ja RUNNING")
            else:
                if existing:
                    # Delete banned/failed + recreate
                    await c.delete(
                        f"https://accounts.cloud.databricks.com/api/2.0/accounts/{account_id}/workspaces/{existing['workspace_id']}",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    await asyncio.sleep(10)

                create_resp = await c.post(
                    f"https://accounts.cloud.databricks.com/api/2.0/accounts/{account_id}/workspaces",
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "workspace_name": workspace_name,
                        "aws_region": region,
                        "credentials_id": credentials_id,
                        "storage_configuration_id": storage_config_id,
                        "network_id": network_id,
                        "pricing_tier": "PREMIUM",
                    },
                )
                create_resp.raise_for_status()
                workspace = create_resp.json()
                ctx.shared.databricks_workspace_created = True
                await ctx.info(f"Workspace PROVISIONING: {workspace['deployment_name']}")

                # Poll RUNNING
                workspace_id = workspace["workspace_id"]
                for _ in range(60):  # 10min max
                    await asyncio.sleep(10)
                    status_resp = await c.get(
                        f"https://accounts.cloud.databricks.com/api/2.0/accounts/{account_id}/workspaces/{workspace_id}",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    status_resp.raise_for_status()
                    workspace = status_resp.json()
                    if workspace.get("workspace_status") == "RUNNING":
                        break
                    await ctx.info(f"Status: {workspace.get('workspace_status')}")
                else:
                    raise TimeoutError(
                        f"Workspace {workspace_name} nao entrou em RUNNING em 10min"
                    )

            host = f"https://{workspace['workspace_fqdn']}"
            ctx.shared.databricks_workspace_id = workspace["workspace_id"]
            ctx.shared.databricks_workspace_host = host
            await ctx.info(f"Workspace RUNNING: {host}")

            # SCIM: add admin user + admins group
            await self._add_admin_user(c, host, token, admin_email)

            # Gerar PAT via OAuth
            pat_resp = await c.post(
                f"{host}/api/2.0/token/create",
                headers={"Authorization": f"Bearer {token}"},
                json={"lifetime_seconds": 0, "comment": "flowertex-deploy-saga"},
            )
            pat_resp.raise_for_status()
            pat = pat_resp.json()["token_value"]
            # Atualiza credentials in-memory (secrets step roda depois e usa essa)
            ctx.credentials.databricks_host = host
            ctx.credentials.databricks_token = pat

            await ctx.success(f"Workspace {workspace_name} pronto + admin + PAT")

    async def _adopt_existing_workspace(
        self,
        ctx: StepContext,
        account_id: str,
        client_id: str,
        secret: str,
        workspace_id: str,
    ) -> None:
        """Hidrata ctx.shared a partir de workspace ja existente.

        Usado quando usuario seleciona workspace_mode=existing no wizard.
        Pula creation flow inteiro — assume infra AWS + UC ja em ordem.
        """
        async with httpx.AsyncClient(timeout=60.0) as c:
            token = await self._get_oauth_token(c, account_id, client_id, secret)
            ws_resp = await c.get(
                f"https://accounts.cloud.databricks.com/api/2.0/accounts/{account_id}/workspaces/{workspace_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            ws_resp.raise_for_status()
            ws = ws_resp.json()
            if ws.get("workspace_status") != "RUNNING":
                raise RuntimeError(
                    f"Workspace {workspace_id} status={ws.get('workspace_status')} — "
                    "so RUNNING pode ser adotado"
                )

            host = f"https://{ws['workspace_fqdn']}"
            ctx.shared.databricks_workspace_id = ws["workspace_id"]
            ctx.shared.databricks_workspace_host = host
            ctx.shared.databricks_network_id = ws.get("network_id")
            ctx.shared.databricks_credentials_id = ws.get("credentials_id")
            ctx.shared.databricks_storage_config_id = ws.get("storage_configuration_id")
            ctx.credentials.databricks_host = host

            # PAT existente passado via credentials override no wizard,
            # OU gerado agora se OAuth permitir (workspace pode aceitar
            # OAuth token diretamente sem precisar de PAT pra alguns endpoints).
            existing_pat = ctx.credentials.databricks_token
            if not existing_pat:
                pat_resp = await c.post(
                    f"{host}/api/2.0/token/create",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"lifetime_seconds": 0, "comment": "flowertex-deploy-saga"},
                )
                if pat_resp.status_code == 200:
                    ctx.credentials.databricks_token = pat_resp.json()["token_value"]
                    await ctx.info("PAT gerado via OAuth no workspace existente")
                else:
                    await ctx.warn(
                        f"Nao foi possivel gerar PAT via OAuth (HTTP {pat_resp.status_code}). "
                        "Steps subsequentes podem falhar — passe databricks_token no wizard."
                    )

            await ctx.success(
                f"Workspace existente adotado: {host} (id={workspace_id})"
            )

    @staticmethod
    async def _get_oauth_token(c, account_id, client_id, secret) -> str:
        resp = await c.post(
            f"https://accounts.cloud.databricks.com/oidc/accounts/{account_id}/v1/token",
            auth=(client_id, secret),
            data={"grant_type": "client_credentials", "scope": "all-apis"},
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    @staticmethod
    async def _add_admin_user(c, host: str, token: str, email: str) -> None:
        # Create user
        user_resp = await c.post(
            f"{host}/api/2.0/preview/scim/v2/Users",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
                "userName": email,
                "entitlements": [
                    {"value": "workspace-access"},
                    {"value": "databricks-sql-access"},
                    {"value": "allow-cluster-create"},
                ],
            },
        )
        if user_resp.status_code not in (200, 201, 409):
            user_resp.raise_for_status()
        if user_resp.status_code == 409:
            # Already exists — lookup
            lookup = await c.get(
                f"{host}/api/2.0/preview/scim/v2/Users?filter=userName+eq+%22{email}%22",
                headers={"Authorization": f"Bearer {token}"},
            )
            lookup.raise_for_status()
            user_id = lookup.json()["Resources"][0]["id"]
        else:
            user_id = user_resp.json()["id"]

        # Add to admins group
        grp_resp = await c.get(
            f"{host}/api/2.0/preview/scim/v2/Groups?filter=displayName+eq+%22admins%22",
            headers={"Authorization": f"Bearer {token}"},
        )
        grp_resp.raise_for_status()
        grp_id = grp_resp.json()["Resources"][0]["id"]

        await c.patch(
            f"{host}/api/2.0/preview/scim/v2/Groups/{grp_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                "Operations": [{
                    "op": "add", "path": "members",
                    "value": [{"value": user_id}],
                }],
            },
        )
