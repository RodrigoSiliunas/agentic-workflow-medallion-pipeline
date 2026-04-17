"""Testes dos tipos base do observer.chat (T7 F2)."""

from __future__ import annotations

import dataclasses

import pytest

from observer.chat.base import (
    ChatEndEvent,
    ChatErrorEvent,
    ChatTokenEvent,
    ChatToolUseEvent,
    ToolSpec,
)


class TestToolSpec:
    def test_to_anthropic_dict_has_expected_shape(self):
        t = ToolSpec(
            name="list_jobs",
            description="Lista jobs",
            input_schema={"type": "object", "properties": {"limit": {"type": "integer"}}},
        )
        d = t.to_anthropic_dict()
        assert d == {
            "name": "list_jobs",
            "description": "Lista jobs",
            "input_schema": {"type": "object", "properties": {"limit": {"type": "integer"}}},
        }

    def test_tool_spec_is_frozen(self):
        t = ToolSpec(name="x", description="y", input_schema={})
        with pytest.raises(dataclasses.FrozenInstanceError):
            t.name = "z"  # type: ignore[misc]


class TestChatEvents:
    def test_token_event(self):
        e = ChatTokenEvent(text="Hello")
        assert e.type == "token"
        assert e.text == "Hello"

    def test_tool_use_event(self):
        e = ChatToolUseEvent(id="tool_1", name="foo", input={"a": 1})
        assert e.type == "tool_use"
        assert e.input == {"a": 1}

    def test_end_event_defaults(self):
        e = ChatEndEvent()
        assert e.type == "end"
        assert e.content_blocks == []
        assert e.output_tokens == 0

    def test_error_event(self):
        e = ChatErrorEvent(message="boom", exception_type="RuntimeError")
        assert e.type == "error"
        assert e.message == "boom"
        assert e.exception_type == "RuntimeError"
