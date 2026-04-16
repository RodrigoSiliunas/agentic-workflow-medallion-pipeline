"""observer.chat — streaming chat with tool use (T7 F2).

Separada da API `diagnose()` (single-shot) para suportar consumidores
que precisam de streaming token-a-token + tool use loop, como o
backend conversacional da plataforma.

Ver `docs/plans/t7-deferred-followup.md` e ADR 0003.
"""

from observer.chat.base import (
    ChatEndEvent,
    ChatErrorEvent,
    ChatEvent,
    ChatLLMProvider,
    ChatTokenEvent,
    ChatToolUseEvent,
    ToolSpec,
)
from observer.chat.registry import (
    CHAT_PROVIDER_REGISTRY,
    create_chat_provider,
    register_chat_provider,
)

__all__ = [
    "CHAT_PROVIDER_REGISTRY",
    "ChatEndEvent",
    "ChatErrorEvent",
    "ChatEvent",
    "ChatLLMProvider",
    "ChatTokenEvent",
    "ChatToolUseEvent",
    "ToolSpec",
    "create_chat_provider",
    "register_chat_provider",
]
