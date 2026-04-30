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
from app.core.url_validator import UnsafeURLError, validate_databricks_workspace_host
from app.database.session import get_db
from app.services.credential_service import CredentialService
from app.services.databricks_oauth import (
    account_oauth_token,
    get_account_oauth_creds,
)

logger = structlog.get_logger()

router = APIRouter()


async def _get_account_oauth(
    company_id, db: AsyncSession,
) -> tuple[str, str, str] | None:
    return await get_account_oauth_creds(CredentialService(db), company_id)


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
            token = await account_oauth_token(c, account_id, client_id, secret)
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
        token = await account_oauth_token(c, account_id, client_id, secret)
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


@router.get("/node-types")
async def list_node_types(
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lista node types suportados pelo workspace alvo.

    Workspace tier (Premium/Enterprise) + region restringe lista. Frontend
    filtra catalogo curado contra essa lista pra evitar oferecer t-series
    em workspace Premium (ex: deploy fail "node type not supported").
    """
    svc = CredentialService(db)
    host = await svc.get_decrypted(auth.company_id, "databricks_host")
    token = await svc.get_decrypted(auth.company_id, "databricks_token")
    if not host or not token:
        return {"workspace_configured": False, "node_types": []}

    try:
        safe_host = validate_databricks_workspace_host(host)
    except UnsafeURLError as exc:
        logger.warning("databricks_host bloqueado por SSRF guard", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"databricks_host invalido: {exc}",
        ) from exc

    async with httpx.AsyncClient(timeout=15.0) as c:
        try:
            resp = await c.get(
                f"{safe_host}/api/2.0/clusters/list-node-types",
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("node-types fetch failed", error=str(exc))
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Databricks list-node-types erro: {exc}",
            ) from exc
        node_types = resp.json().get("node_types", []) or []

    return {
        "workspace_configured": True,
        "node_types": [
            {
                "node_type_id": n.get("node_type_id"),
                "memory_mb": n.get("memory_mb"),
                "num_cores": n.get("num_cores"),
                "category": n.get("category"),
                "instance_type_id": (n.get("instance_type_id") or {}),
            }
            for n in node_types
        ],
    }


@router.get("/policies")
async def list_cluster_policies(
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lista cluster policies do workspace alvo.

    Policies sao workspace-level (nao account). Usa databricks_host +
    databricks_token das company credentials. Se faltar host/token,
    retorna 200 com lista vazia + flag.
    """
    svc = CredentialService(db)
    host = await svc.get_decrypted(auth.company_id, "databricks_host")
    token = await svc.get_decrypted(auth.company_id, "databricks_token")
    if not host or not token:
        return {"workspace_configured": False, "policies": []}

    try:
        safe_host = validate_databricks_workspace_host(host)
    except UnsafeURLError as exc:
        logger.warning("databricks_host bloqueado por SSRF guard", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"databricks_host invalido: {exc}",
        ) from exc

    async with httpx.AsyncClient(timeout=15.0) as c:
        try:
            resp = await c.get(
                f"{safe_host}/api/2.0/policies/clusters/list",
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("policies fetch failed", error=str(exc))
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Databricks policies API erro: {exc}",
            ) from exc
        policies = resp.json().get("policies", []) or []

    return {
        "workspace_configured": True,
        "policies": [
            {
                "policy_id": p.get("policy_id"),
                "name": p.get("name"),
                "description": p.get("description"),
                "definition": p.get("definition"),
            }
            for p in policies
        ],
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
        token = await account_oauth_token(c, account_id, client_id, secret)
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
