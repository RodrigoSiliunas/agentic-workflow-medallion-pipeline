"""Testes do registry/factory do observer.chat (T7 F2)."""

from __future__ import annotations

import pytest

from observer.chat.registry import (
    CHAT_PROVIDER_REGISTRY,
    create_chat_provider,
    list_chat_providers,
    register_chat_provider,
)


def test_anthropic_registered_by_import():
    # Import do módulo `anthropic.py` popula o registry via decorator
    providers = list_chat_providers()
    assert "anthropic" in providers


def test_create_anthropic_returns_protocol_impl():
    p = create_chat_provider("anthropic", api_key="sk-test")
    # Duck-type: tem método `stream_with_tools` async
    assert hasattr(p, "stream_with_tools")
    assert p.name == "anthropic"


def test_create_unknown_raises_valueerror():
    with pytest.raises(ValueError, match="não encontrado"):
        create_chat_provider("gemini-2")


def test_register_decorator_adds_entry():
    @register_chat_provider("__test-chat__")
    class _TestChat:
        name = "__test-chat__"

        async def stream_with_tools(self, **kwargs):
            yield {"type": "token", "text": "x"}

    try:
        assert CHAT_PROVIDER_REGISTRY["__test-chat__"] is _TestChat
    finally:
        CHAT_PROVIDER_REGISTRY.pop("__test-chat__", None)


def test_register_decorator_sets_name_if_missing():
    @register_chat_provider("__no-name__")
    class _NoName:
        async def stream_with_tools(self, **kwargs):
            yield {"type": "token", "text": "x"}

    try:
        assert _NoName.name == "__no-name__"  # type: ignore[attr-defined]
    finally:
        CHAT_PROVIDER_REGISTRY.pop("__no-name__", None)


def test_protocol_is_structural():
    """ChatLLMProvider é Protocol — duck-typed via hasattr."""
    p = create_chat_provider("anthropic", api_key="k")
    # isinstance para Protocol sem @runtime_checkable não funciona,
    # mas a factory garante que o provider concreto satisfaz o contrato.
    assert callable(p.stream_with_tools)
