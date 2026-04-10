"""Factory e registry para LLM e Git providers.

Uso:
    from observer.providers import create_llm_provider, create_git_provider

    llm = create_llm_provider("anthropic", api_key="sk-...")
    git = create_git_provider("github", token="ghp_...", repo="owner/repo")

    result = llm.diagnose(request)
    pr = git.create_fix_pr(result, "bronze_ingestion")

Providers disponíveis:
    LLM: anthropic, openai, ollama
    Git: github
"""

from __future__ import annotations

import contextlib

from observer.providers.base import (
    DiagnosisRequest as DiagnosisRequest,
)
from observer.providers.base import (
    DiagnosisResult as DiagnosisResult,
)
from observer.providers.base import (
    GitProvider as GitProvider,
)
from observer.providers.base import (
    LLMProvider as LLMProvider,
)
from observer.providers.base import (
    PRResult as PRResult,
)

# Registry de providers
_llm_registry: dict[str, type[LLMProvider]] = {}
_git_registry: dict[str, type[GitProvider]] = {}


def register_llm_provider(name: str):
    """Decorator para registrar um LLM provider na factory."""
    def decorator(cls: type[LLMProvider]):
        _llm_registry[name] = cls
        return cls
    return decorator


def register_git_provider(name: str):
    """Decorator para registrar um Git provider na factory."""
    def decorator(cls: type[GitProvider]):
        _git_registry[name] = cls
        return cls
    return decorator


def create_llm_provider(name: str, **kwargs) -> LLMProvider:
    """Factory: cria instância de LLM provider pelo nome.

    Args:
        name: Nome do provider (anthropic, openai, ollama)
        **kwargs: Parâmetros do provider (api_key, model, base_url, etc)

    Raises:
        ValueError: Se provider não registrado
    """
    # Lazy import dos providers para registrar no registry
    _ensure_providers_loaded()

    if name not in _llm_registry:
        available = ", ".join(_llm_registry.keys()) or "nenhum"
        raise ValueError(
            f"LLM provider '{name}' não encontrado. "
            f"Disponíveis: {available}"
        )
    return _llm_registry[name](**kwargs)


def create_git_provider(name: str, **kwargs) -> GitProvider:
    """Factory: cria instância de Git provider pelo nome.

    Args:
        name: Nome do provider (github, gitlab)
        **kwargs: Parâmetros do provider (token, repo, base_branch, etc)

    Raises:
        ValueError: Se provider não registrado
    """
    _ensure_providers_loaded()

    if name not in _git_registry:
        available = ", ".join(_git_registry.keys()) or "nenhum"
        raise ValueError(
            f"Git provider '{name}' não encontrado. "
            f"Disponíveis: {available}"
        )
    return _git_registry[name](**kwargs)


def list_providers() -> dict[str, list[str]]:
    """Lista todos os providers registrados."""
    _ensure_providers_loaded()
    return {
        "llm": list(_llm_registry.keys()),
        "git": list(_git_registry.keys()),
    }


def _ensure_providers_loaded():
    """Lazy import dos módulos de providers para popular o registry."""
    if not _llm_registry:
        with contextlib.suppress(ImportError):
            import observer.providers.anthropic_provider  # noqa: F401
        with contextlib.suppress(ImportError):
            import observer.providers.openai_provider  # noqa: F401
    if not _git_registry:
        with contextlib.suppress(ImportError):
            import observer.providers.github_provider  # noqa: F401
