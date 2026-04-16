"""Step `upload` — clona/atualiza o repo no Databricks via Repos API.

Requer classic PAT (ghp_*). Fine-grained tokens (github_pat_*) NAO funcionam
com Databricks Repos.
"""

from __future__ import annotations

import asyncio
import contextlib

from databricks.sdk.errors import ResourceAlreadyExists

from app.services.real_saga.base import StepContext
from app.services.real_saga.databricks_client import workspace_client
from app.services.real_saga.registry import register_saga_step


@register_saga_step("upload")
class UploadStep:
    step_id = "upload"

    async def execute(self, ctx: StepContext) -> None:
        github_repo = ctx.credentials.github_repo
        if not github_repo:
            raise ValueError("github_repo nao configurado em credentials")

        repo_url = f"https://github.com/{github_repo}.git"
        branch = ctx.env_vars().get("git_branch", "main")

        w = workspace_client(ctx.credentials)

        # Configurar Git credential com o classic PAT
        if ctx.credentials.github_token:
            await self._ensure_git_credential(ctx, w)

        def _user_name() -> str:
            return w.current_user.me().user_name or "unknown"

        user = await asyncio.to_thread(_user_name)
        repo_name = github_repo.split("/")[-1]
        repo_path = f"/Repos/{user}/{repo_name}"

        await ctx.info(f"Sincronizando repo {repo_url}@{branch} -> {repo_path}")

        # Criar ou atualizar o repo
        existing = await self._find_repo(w, repo_path)
        if existing is None:
            await self._create(ctx, w, repo_url, repo_path, branch)
        else:
            await self._update(ctx, w, existing, branch)

        await ctx.success(f"Repo sincronizado: {repo_path}")
        ctx.shared.repo_path = repo_path

    @staticmethod
    async def _ensure_git_credential(ctx: StepContext, w) -> None:
        token = ctx.credentials.github_token

        def _ensure() -> None:
            creds = list(w.git_credentials.list())
            if creds:
                w.git_credentials.update(
                    credential_id=creds[0].credential_id,
                    git_provider="gitHub",
                    git_username="deploy-bot",
                    personal_access_token=token,
                )
            else:
                w.git_credentials.create(
                    git_provider="gitHub",
                    git_username="deploy-bot",
                    personal_access_token=token,
                )

        await asyncio.to_thread(_ensure)
        await ctx.info("Git credential configurado")

    @staticmethod
    async def _find_repo(w, path: str):
        def _search():
            for repo in w.repos.list():
                if repo.path == path:
                    return repo
            return None

        return await asyncio.to_thread(_search)

    @staticmethod
    async def _create(ctx: StepContext, w, url: str, path: str, branch: str) -> None:
        def _do():
            with contextlib.suppress(ResourceAlreadyExists):
                return w.repos.create(url=url, provider="gitHub", path=path)

        await asyncio.to_thread(_do)
        await ctx.info(f"Repo criado: {path}")
        found = await UploadStep._find_repo(w, path)
        if found is not None:
            await UploadStep._update(ctx, w, found, branch)

    @staticmethod
    async def _update(ctx: StepContext, w, repo, branch: str) -> None:
        def _do():
            w.repos.update(repo_id=repo.id, branch=branch)

        await asyncio.to_thread(_do)
        await ctx.info(f"Repo atualizado para branch {branch}")
