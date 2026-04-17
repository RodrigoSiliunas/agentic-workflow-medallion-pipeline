"""Registry + factory para `ChatLLMProvider` (T7 F2)."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from observer.chat.base import ChatLLMProvider

CHAT_PROVIDER_REGISTRY: dict[str, type[ChatLLMProvider]] = {}


def register_chat_provider(name: str):
    """Decorator que registra um ChatLLMProvider no registry."""

    def decorator(cls: type[ChatLLMProvider]) -> type[ChatLLMProvider]:
        CHAT_PROVIDER_REGISTRY[name] = cls
        if not getattr(cls, "name", None):
            cls.name = name  # type: ignore[attr-defined]
        return cls

    return decorator


def create_chat_provider(name: str, **kwargs) -> ChatLLMProvider:
    """Factory: cria instância de ChatLLMProvider pelo nome.

    Args:
        name: identificador registrado (ex: `"anthropic"`)
        **kwargs: kwargs forwarded ao constructor (api_key, etc).

    Raises:
        ValueError: provider não registrado.
    """
    _ensure_loaded()
    cls = CHAT_PROVIDER_REGISTRY.get(name)
    if cls is None:
        available = ", ".join(sorted(CHAT_PROVIDER_REGISTRY)) or "nenhum"
        raise ValueError(
            f"Chat provider '{name}' não encontrado. Disponíveis: {available}"
        )
    return cls(**kwargs)


def list_chat_providers() -> list[str]:
    _ensure_loaded()
    return sorted(CHAT_PROVIDER_REGISTRY)


def _ensure_loaded() -> None:
    """Lazy import dos módulos de provider pra popular o registry.

    Segue mesmo padrão do `observer.providers._ensure_providers_loaded`.
    """
    if not CHAT_PROVIDER_REGISTRY:
        with contextlib.suppress(ImportError):
            import observer.chat.anthropic  # noqa: F401
