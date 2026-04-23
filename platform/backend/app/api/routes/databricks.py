"""Databricks introspection routes — wizard one-click deploy.

Expoe metadata do Databricks Account pra UI permitir o usuario:
- Listar workspaces existentes (modo "usar workspace existente")
- Inspecionar config de um workspace alvo (network, credentials, root bucket)
- Listar metastores (advanced)

Usa OAuth M2M do Databricks Account (vem das company credentials cifradas
no Postgres). Se o usuario nao configurou OAuth ainda, retorna 200 com
lista vazia + flag indicando.
"""

from __future__ import annotations

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_current_user
from app.database.session import get_db
from app.services.credential_service import CredentialService

logger = structlog.get_logger()

router = APIRouter()


async def _get_account_oauth(
    company_id, db: AsyncSession,
) -> tuple[str, str, str] | None:
    """Resolve account_id + OAuth client_id + secret a partir das credenciais.

    Retorna None se faltar qualquer um — caller deve responder 200 com
    `oauth_configured: false` em vez de 500.
    """
    svc = CredentialService(db)
    account_id = await svc.get_decrypted(company_id, "databricks_account_id")
    client_id = await svc.get_decrypted(company_id, "databricks_oauth_client_id")
    secret = await svc.get_decrypted(company_id, "databricks_oauth_secret")
    if not all([account_id, client_id, secret]):
        return None
    return account_id, client_id, secret


async def _account_token(
    c: httpx.AsyncClient, account_id: str, client_id: str, secret: str,
) -> str:
    resp = await c.post(
        f"https://accounts.cloud.databricks.com/oidc/accounts/{account_id}/v1/token",
        auth=(client_id, secret),
        data={"grant_type": "client_credentials", "scope": "all-apis"},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


@router.get("/workspaces")
async def list_workspaces(
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lista workspaces da Databricks Account.

    Resposta:
        {
          "oauth_configured": bool,
          "workspaces": [
            {
              "workspace_id": int,
              "workspace_name": str,
              "deployment_name": str,
              "workspace_status": "RUNNING" | ...,
              "aws_region": str,
              "has_network": bool,        # network_id presente
              "has_storage_config": bool, # storage_configuration_id presente
            }
          ]
        }
    """
    oauth = await _get_account_oauth(auth.company_id, db)
    if not oauth:
        return {"oauth_configured": False, "workspaces": []}

    account_id, client_id, secret = oauth

    try:
        async with httpx.AsyncClient(timeout=30.0) as c:
            token = await _account_token(c, account_id, client_id, secret)
            resp = await c.get(
                f"https://accounts.cloud.databricks.com/api/2.0/accounts/{account_id}/workspaces",
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            workspaces = resp.json() or []
    except httpx.HTTPError as exc:
        logger.warning("databricks list_workspaces failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Falha ao consultar Databricks Account API",
        ) from exc

    return {
        "oauth_configured": True,
        "workspaces": [
            {
                "workspace_id": w.get("workspace_id"),
                "workspace_name": w.get("workspace_name"),
                "deployment_name": w.get("deployment_name"),
                "workspace_status": w.get("workspace_status"),
                "aws_region": w.get("aws_region"),
                "has_network": bool(w.get("network_id")),
                "has_storage_config": bool(w.get("storage_configuration_id")),
            }
            for w in workspaces
        ],
    }


@router.get("/workspaces/{workspace_id}/config")
async def get_workspace_config(
    workspace_id: int,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Introspect completo de um workspace — usado pra autofill no wizard.

    Resposta:
        {
          "workspace_id": int,
          "workspace_name": str,
          "deployment_name": str,
          "workspace_status": str,
          "aws_region": str,
          "network_id": str | None,
          "credentials_id": str | None,
          "storage_configuration_id": str | None,
          "root_bucket_name": str | None,
          "metastore_id": str | None,
          "metastore_attached": bool,
        }
    """
    oauth = await _get_account_oauth(auth.company_id, db)
    if not oauth:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Databricks Account OAuth nao configurado em /settings",
        )

    account_id, client_id, secret = oauth

    async with httpx.AsyncClient(timeout=30.0) as c:
        token = await _account_token(c, account_id, client_id, secret)
        ws_resp = await c.get(
            f"https://accounts.cloud.databricks.com/api/2.0/accounts/{account_id}/workspaces/{workspace_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        if ws_resp.status_code == 404:
            raise HTTPException(status_code=404, detail="Workspace nao encontrado")
        ws_resp.raise_for_status()
        ws = ws_resp.json()

        # Resolve root bucket via storage_configuration_id
        root_bucket: str | None = None
        sc_id = ws.get("storage_configuration_id")
        if sc_id:
            sc_resp = await c.get(
                f"https://accounts.cloud.databricks.com/api/2.0/accounts/{account_id}/storage-configurations/{sc_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            if sc_resp.status_code == 200:
                root_bucket = (
                    sc_resp.json().get("root_bucket_info", {}).get("bucket_name")
                )

        # Metastore attachment
        metastore_id: str | None = None
        ms_resp = await c.get(
            f"https://accounts.cloud.databricks.com/api/2.0/accounts/{account_id}/workspaces/{workspace_id}/metastore",
            headers={"Authorization": f"Bearer {token}"},
        )
        if ms_resp.status_code == 200:
            metastore_id = ms_resp.json().get("metastore_id")

    return {
        "workspace_id": ws.get("workspace_id"),
        "workspace_name": ws.get("workspace_name"),
        "deployment_name": ws.get("deployment_name"),
        "workspace_status": ws.get("workspace_status"),
        "aws_region": ws.get("aws_region"),
        "network_id": ws.get("network_id"),
        "credentials_id": ws.get("credentials_id"),
        "storage_configuration_id": sc_id,
        "root_bucket_name": root_bucket,
        "metastore_id": metastore_id,
        "metastore_attached": bool(metastore_id),
    }


@router.get("/metastores")
async def list_metastores(
    region: str | None = None,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lista metastores da Account, opcionalmente filtrando por regiao."""
    oauth = await _get_account_oauth(auth.company_id, db)
    if not oauth:
        return {"oauth_configured": False, "metastores": []}

    account_id, client_id, secret = oauth

    async with httpx.AsyncClient(timeout=30.0) as c:
        token = await _account_token(c, account_id, client_id, secret)
        resp = await c.get(
            f"https://accounts.cloud.databricks.com/api/2.0/accounts/{account_id}/metastores",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        metastores = resp.json().get("metastores", []) or []

    if region:
        metastores = [m for m in metastores if m.get("region") == region]

    return {
        "oauth_configured": True,
        "metastores": [
            {
                "metastore_id": m.get("metastore_id"),
                "name": m.get("name"),
                "region": m.get("region"),
                "default_data_access_config_id": m.get("default_data_access_config_id"),
            }
            for m in metastores
        ],
    }
