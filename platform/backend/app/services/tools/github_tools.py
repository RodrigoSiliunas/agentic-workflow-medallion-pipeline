"""Tools que consomem `GitHubService` (T7 F4)."""

from __future__ import annotations

from typing import Any

from app.services.tools.base import ToolContext, register_tool


@register_tool("read_file")
class ReadFile:
    name = "read_file"
    description = "Le conteudo de um arquivo do repositorio do pipeline."
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "ref": {"type": "string", "default": "main"},
        },
        "required": ["path"],
    }

    async def run(self, ctx: ToolContext, input_data: dict[str, Any]) -> dict[str, Any]:
        content = await ctx.github.read_file(
            input_data["path"], input_data.get("ref", "main")
        )
        return {"path": input_data["path"], "content": content}


@register_tool("list_recent_prs")
class ListRecentPrs:
    name = "list_recent_prs"
    description = "Lista PRs recentes do repositorio."
    input_schema = {
        "type": "object",
        "properties": {
            "state": {"type": "string", "default": "all"},
            "limit": {"type": "integer", "default": 10},
        },
    }

    async def run(self, ctx: ToolContext, input_data: dict[str, Any]) -> dict[str, Any]:
        prs = await ctx.github.list_recent_prs(
            input_data.get("state", "all"),
            input_data.get("limit", 10),
        )
        return {"prs": prs}


@register_tool("get_pr_diff")
class GetPrDiff:
    name = "get_pr_diff"
    description = "Mostra o diff de um PR — arquivos alterados e o patch."
    input_schema = {
        "type": "object",
        "properties": {"pr_number": {"type": "integer"}},
        "required": ["pr_number"],
    }

    async def run(self, ctx: ToolContext, input_data: dict[str, Any]) -> dict[str, Any]:
        return await ctx.github.get_pr_diff(input_data["pr_number"])


@register_tool("create_pull_request")
class CreatePullRequest:
    name = "create_pull_request"
    description = "Cria PR com mudancas no codigo. REQUER CONFIRMACAO."
    input_schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "description": {"type": "string"},
            "branch": {"type": "string"},
            "files": {
                "type": "object",
                "description": "Dict path->content dos arquivos a modificar",
            },
        },
        "required": ["title", "description", "branch"],
    }
    requires_confirmation = True

    async def run(self, ctx: ToolContext, input_data: dict[str, Any]) -> dict[str, Any]:
        branch = f"feat/{ctx.user_name}/{input_data['branch']}"
        return await ctx.github.create_pr(
            title=input_data["title"],
            body=input_data["description"],
            branch=branch,
            files=input_data.get("files"),
        )
