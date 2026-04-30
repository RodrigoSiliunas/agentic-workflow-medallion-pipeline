"""Helpers compartilhados pra OAuth M2M do Databricks Account.

Antes essa logica vivia duplicada em 6+ lugares (routes/databricks.py +
5 saga steps). Cada um tinha seu proprio `_get_oauth_token` / `_get_token`
com mesma URL hardcoded. Extracao reduz drift quando muda scope ou URL.
"""

from __future__ import annotations

import uuid

import httpx

from app.services.credential_service import CredentialService

ACCOUNT_BASE_URL = "https://accounts.cloud.databricks.com"


async def account_oauth_token(
    client: httpx.AsyncClient,
    account_id: str,
    client_id: str,
    secret: str,
    *,
    scope: str = "all-apis",
) -> str:
    """OAuth M2M client_credentials flow → access_token (Account-level).

    Token expira em ~1h; saga steps tipicamente pegam um por execucao.
    Levanta httpx.HTTPStatusError em 4xx/5xx — caller decide como tratar.
    """
    resp = await client.post(
        f"{ACCOUNT_BASE_URL}/oidc/accounts/{account_id}/v1/token",
        auth=(client_id, secret),
        data={"grant_type": "client_credentials", "scope": scope},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


async def get_account_oauth_creds(
    svc: CredentialService, company_id: uuid.UUID
) -> tuple[str, str, str] | None:
    """Resolve (account_id, client_id, secret) das credenciais cifradas.

    Retorna None se faltar QUALQUER um dos tres — o caller tipicamente
    responde 200 com `oauth_configured: false` ou pula step opcional.
    """
    account_id = await svc.get_decrypted(company_id, "databricks_account_id")
    client_id = await svc.get_decrypted(company_id, "databricks_oauth_client_id")
    secret = await svc.get_decrypted(company_id, "databricks_oauth_secret")
    if not all([account_id, client_id, secret]):
        return None
    return account_id, client_id, secret
