"""Step `validate` — verifica que todas as credenciais do deploy funcionam.

Faz 4 pings em paralelo:
- AWS STS GetCallerIdentity via boto3
- Databricks `current_user.me()` via WorkspaceClient
- Anthropic `/v1/models` via httpx (apenas se a key existir)
- GitHub `/user` via httpx (apenas se o token existir)

Falha o step na primeira credencial obrigatoria invalida. Credenciais opcionais
(anthropic, github) so viram warning.
"""

from __future__ import annotations

import asyncio

import httpx

from app.services.real_saga.aws_client import boto3_session
from app.services.real_saga.base import CredentialMissingError, StepContext
from app.services.real_saga.databricks_client import workspace_client
from app.services.real_saga.registry import register_saga_step


@register_saga_step("validate")
class ValidateStep:
    step_id = "validate"

    async def execute(self, ctx: StepContext) -> None:
        await ctx.info("Validando credenciais do deploy (4 checks em paralelo)...")

        # Checks obrigatorios (AWS + Databricks) levantam exception se falham.
        # Checks opcionais (Anthropic + GitHub) so emitem warning.
        # Rodamos todos em paralelo — gather propaga a primeira exception.
        await asyncio.gather(
            self._check_aws(ctx),
            self._check_databricks(ctx),
            self._check_anthropic(ctx),
            self._check_github(ctx),
        )

        await ctx.success("Todas as credenciais validas — prosseguindo.")

    @staticmethod
    async def _check_aws(ctx: StepContext) -> None:
        try:
            session = boto3_session(ctx.credentials)
        except CredentialMissingError as exc:
            await ctx.error(str(exc))
            raise

        def _sts_call() -> dict[str, str]:
            sts = session.client("sts")
            return sts.get_caller_identity()

        identity = await asyncio.to_thread(_sts_call)
        account = identity.get("Account", "?")
        arn = identity.get("Arn", "?")
        await ctx.info(f"AWS STS OK — account={account} arn={arn}")

    @staticmethod
    async def _check_databricks(ctx: StepContext) -> None:
        try:
            w = workspace_client(ctx.credentials)
        except CredentialMissingError as exc:
            await ctx.error(str(exc))
            raise

        me = await asyncio.to_thread(lambda: w.current_user.me())
        await ctx.info(
            f"Databricks OK — workspace={ctx.credentials.databricks_host} user={me.user_name}"
        )

    @staticmethod
    async def _check_anthropic(ctx: StepContext) -> None:
        key = ctx.credentials.anthropic_api_key
        if not key:
            await ctx.warn("Anthropic API key nao configurada — Observer Agent nao vai rodar.")
            return
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://api.anthropic.com/v1/models",
                    headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
                )
            if resp.status_code == 200:
                await ctx.info("Anthropic API OK (Claude disponivel)")
            else:
                await ctx.warn(
                    f"Anthropic API retornou HTTP {resp.status_code} — Observer pode nao funcionar."
                )
        except httpx.HTTPError as exc:
            await ctx.warn(f"Anthropic API ping falhou: {exc}")

    @staticmethod
    async def _check_github(ctx: StepContext) -> None:
        token = ctx.credentials.github_token
        if not token:
            await ctx.warn(
                "GitHub token nao configurado — Observer nao abrira PRs automaticamente."
            )
            return
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://api.github.com/user",
                    headers={"Authorization": f"Bearer {token}"},
                )
            if resp.status_code == 200:
                login = resp.json().get("login", "?")
                await ctx.info(f"GitHub OK — autenticado como {login}")
            else:
                await ctx.warn(f"GitHub API retornou HTTP {resp.status_code}")
        except httpx.HTTPError as exc:
            await ctx.warn(f"GitHub API ping falhou: {exc}")
