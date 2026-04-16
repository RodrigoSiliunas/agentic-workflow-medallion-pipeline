"""Tipos + registry base das tools consumidas pelo LLMOrchestrator."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from observer.chat import ToolSpec

if TYPE_CHECKING:
    from app.services.databricks_service import DatabricksService
    from app.services.github_service import GitHubService


@dataclass
class ToolContext:
    """Dependências passadas a cada tool em runtime."""

    databricks: DatabricksService
    github: GitHubService
    company_id: uuid.UUID
    user_name: str


class ToolHandler(Protocol):
    """Contrato de uma tool registrada.

    Cada subclasse define `name`, `description`, `input_schema` (JSON Schema)
    e implementa `run(ctx, input_data)` retornando dict.
    """

    name: str
    description: str
    input_schema: dict[str, Any]
    requires_confirmation: bool

    async def run(
        self, ctx: ToolContext, input_data: dict[str, Any]
    ) -> dict[str, Any]: ...


# Registry global populado pelos decorators em cada módulo de tools.
TOOL_REGISTRY: dict[str, type[ToolHandler]] = {}


def register_tool(name: str):
    """Decorator que registra um ToolHandler no `TOOL_REGISTRY`.

    Idempotente contra redecoração. Default `requires_confirmation = False`
    se a classe não declarar.
    """

    def decorator(cls: type[ToolHandler]) -> type[ToolHandler]:
        if not getattr(cls, "name", None):
            cls.name = name  # type: ignore[attr-defined]
        if not hasattr(cls, "requires_confirmation"):
            cls.requires_confirmation = False  # type: ignore[attr-defined]
        TOOL_REGISTRY[name] = cls
        return cls

    return decorator


def all_tool_specs() -> list[ToolSpec]:
    """Lista de `ToolSpec` para passar ao ChatLLMProvider."""
    return [
        ToolSpec(
            name=cls.name,
            description=cls.description,
            input_schema=cls.input_schema,
        )
        for cls in TOOL_REGISTRY.values()
    ]


def confirmation_required_tools() -> set[str]:
    """Nomes de tools que exigem confirmação antes de executar."""
    return {
        name
        for name, cls in TOOL_REGISTRY.items()
        if getattr(cls, "requires_confirmation", False)
    }
