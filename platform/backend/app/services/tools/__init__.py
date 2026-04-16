"""Tool registry para o LLMOrchestrator (T7 F4).

Decorator `@register_tool` popula `TOOL_REGISTRY`. `all_tool_specs()`
devolve a lista consumida pelo chat provider.

Adicionar tool nova = 1 arquivo novo no diretório + decorator. Sem
edit no orchestrator.
"""

from observer.chat import ToolSpec

# Importa módulos de tools pra popular o registry.
from app.services.tools import databricks_tools as _databricks  # noqa: F401
from app.services.tools import github_tools as _github  # noqa: F401
from app.services.tools import pipeline_tools as _pipeline  # noqa: F401
from app.services.tools.base import (
    TOOL_REGISTRY,
    ToolContext,
    ToolHandler,
    all_tool_specs,
    confirmation_required_tools,
    register_tool,
)

__all__ = [
    "TOOL_REGISTRY",
    "ToolContext",
    "ToolHandler",
    "ToolSpec",
    "all_tool_specs",
    "confirmation_required_tools",
    "register_tool",
]
