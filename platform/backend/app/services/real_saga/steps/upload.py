"""Step `upload` — sincroniza notebooks via Workspace API.

Usa GitHub tarball (requer apenas token + repo, sem Repos/git-clone do Databricks
que depende de workspace root bucket). Upload arquivo-por-arquivo via
workspace.import_ com format=SOURCE. Suporta workspaces onde Repos API
esta quebrado (ex: infra bucket ausente).
"""

from __future__ import annotations

import asyncio
import base64
import io
import tarfile
from pathlib import Path

import httpx
from databricks.sdk.service.workspace import ImportFormat, Language

from app.services.real_saga.base import StepContext
from app.services.real_saga.databricks_client import workspace_client
from app.services.real_saga.registry import register_saga_step

_UPLOAD_BASE = "/Shared/flowertex"


@register_saga_step("upload")
class UploadStep:
    step_id = "upload"

    async def compensate(self, ctx: StepContext) -> None:
        """Rollback: deleta workspace path criado pelo upload (recursive)."""
        if not ctx.shared.databricks_repo_created:
            await ctx.info("compensate(upload): nada uploaded nesta saga — skip")
            return
        path = ctx.shared.repo_path
        if not path:
            return
        w = workspace_client(ctx.credentials)
        try:
            await asyncio.to_thread(
                lambda: w.workspace.delete(path=path, recursive=True)
            )
            await ctx.info(f"compensate(upload): {path} removido")
        except Exception as exc:  # noqa: BLE001
            await ctx.warn(f"compensate(upload) falhou: {exc}")

    async def execute(self, ctx: StepContext) -> None:
        github_repo = ctx.credentials.github_repo
        if not github_repo:
            raise ValueError("github_repo nao configurado em credentials")
        token = ctx.credentials.github_token
        if not token:
            raise ValueError("github_token nao configurado em credentials")

        branch = ctx.env_vars().get("git_branch", "main")
        repo_name = github_repo.split("/")[-1]
        workspace_path = f"{_UPLOAD_BASE}/{repo_name}"

        await ctx.info(f"Baixando tarball {github_repo}@{branch}")
        tar_bytes = await self._fetch_tarball(github_repo, branch, token)

        await ctx.info(f"Extraindo e uploading notebooks -> {workspace_path}")
        w = workspace_client(ctx.credentials)
        count = await self._upload_tarball(ctx, w, tar_bytes, workspace_path)

        await ctx.success(
            f"Notebooks sincronizados: {count} arquivos em {workspace_path}"
        )
        ctx.shared.repo_path = workspace_path
        ctx.shared.databricks_repo_created = True

    @staticmethod
    async def _fetch_tarball(repo: str, branch: str, token: str) -> bytes:
        url = f"https://api.github.com/repos/{repo}/tarball/{branch}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        }
        async with httpx.AsyncClient(follow_redirects=True, timeout=120.0) as client:
            r = await client.get(url, headers=headers)
            r.raise_for_status()
            return r.content

    @staticmethod
    async def _upload_tarball(
        ctx: StepContext, w, tar_bytes: bytes, workspace_base: str
    ) -> int:
        """Extrai tarball + upload cada .py via workspace.import_."""

        # Filtra só .py em pipelines/*/notebooks/ e observer-framework/notebooks/
        def _walk_tar() -> list[tuple[str, bytes]]:
            files: list[tuple[str, bytes]] = []
            with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:gz") as tar:
                for member in tar.getmembers():
                    if not member.isfile():
                        continue
                    # tarball wraps files in {owner}-{repo}-{sha}/ prefix
                    parts = member.name.split("/", 1)
                    if len(parts) < 2:
                        continue
                    rel_path = parts[1]
                    if not (rel_path.endswith(".py") or rel_path.endswith(".yaml")):
                        continue
                    pipe_notebook = (
                        "pipelines/" in rel_path and "/notebooks/" in rel_path
                    )
                    observer_notebook = "observer-framework/notebooks/" in rel_path
                    pipe_lib = (
                        "pipelines/" in rel_path and "/pipeline_lib/" in rel_path
                    )
                    observer_lib = (
                        "observer-framework/observer/" in rel_path
                    )
                    pipe_config = (
                        "pipelines/" in rel_path and "/config/" in rel_path
                    )
                    if not (
                        pipe_notebook
                        or observer_notebook
                        or pipe_lib
                        or observer_lib
                        or pipe_config
                    ):
                        continue
                    f = tar.extractfile(member)
                    if f is None:
                        continue
                    files.append((rel_path, f.read()))
            return files

        files = await asyncio.to_thread(_walk_tar)
        await ctx.info(f"{len(files)} .py relevantes encontrados no tarball")

        dirs_created: set[str] = set()

        def _ensure_dir(workspace_dir: str) -> None:
            if workspace_dir in dirs_created:
                return
            w.workspace.mkdirs(path=workspace_dir)
            dirs_created.add(workspace_dir)

        def _upload_one(rel_path: str, content: bytes) -> None:
            # Pipeline_lib e observer modulos sao Python puro — upload
            # preserva .py pra Python import(). Notebooks executaveis
            # (com header '# Databricks notebook source') viram notebooks
            # sem extension.
            is_raw = (
                "/pipeline_lib/" in rel_path
                or "/observer/" in rel_path
                or rel_path.endswith(".yaml")
            )
            if is_raw:
                # Files API preserva .py + trata como raw file
                ws_path = f"{workspace_base}/{rel_path}"
                ws_dir = ws_path.rsplit("/", 1)[0]
                _ensure_dir(ws_dir)
                w.workspace.upload(
                    path=ws_path,
                    content=content,
                    format=ImportFormat.AUTO,
                    overwrite=True,
                )
            else:
                # Notebook executavel — strip .py, Databricks converte pra notebook
                ws_notebook = f"{workspace_base}/{rel_path[:-3]}"
                ws_dir = ws_notebook.rsplit("/", 1)[0]
                _ensure_dir(ws_dir)
                b64 = base64.b64encode(content).decode("ascii")
                w.workspace.import_(
                    path=ws_notebook,
                    format=ImportFormat.SOURCE,
                    language=Language.PYTHON,
                    content=b64,
                    overwrite=True,
                )

        def _upload_all() -> int:
            # mkdirs do base path primeiro
            w.workspace.mkdirs(path=workspace_base)
            for rel_path, content in files:
                _upload_one(rel_path, content)
            return len(files)

        return await asyncio.to_thread(_upload_all)
