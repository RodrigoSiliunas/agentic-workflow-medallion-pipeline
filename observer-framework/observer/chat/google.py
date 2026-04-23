"""GoogleChatProvider — streaming + tool use via `google-genai` SDK.

Implementa `ChatLLMProvider` protocol pro provider Google Gemini
(Gemini 2.5 Pro, 2.5 Flash, 2.0 Flash). Usa novo SDK unificado
`google.genai` (ex google-generativeai esta deprecated).

Tools: `Tool(function_declarations=[...])` no config.
Streaming: `generate_content_stream()` async iterator.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from observer.chat.base import (
    ChatEndEvent,
    ChatErrorEvent,
    ChatEvent,
    ChatLLMProvider,
    ChatTokenEvent,
    ChatToolUseEvent,
    ToolSpec,
)
from observer.chat.registry import register_chat_provider


def _convert_messages_to_gemini(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Converte historico Anthropic-style pra Gemini Content[].

    Gemini: contents = [{"role": "user|model", "parts": [{"text": "..."}]}]
    "model" eh equivalente a "assistant".
    """
    out: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role", "user")
        gemini_role = "model" if role == "assistant" else "user"
        content = msg.get("content", "")
        parts: list[dict[str, Any]] = []

        if isinstance(content, str):
            parts.append({"text": content})
        elif isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    btype = getattr(block, "type", None)
                    if btype == "text":
                        parts.append({"text": getattr(block, "text", "")})
                    elif btype == "tool_use":
                        parts.append({
                            "function_call": {
                                "name": getattr(block, "name", ""),
                                "args": dict(getattr(block, "input", {}) or {}),
                            }
                        })
                    continue
                btype = block.get("type")
                if btype == "text":
                    parts.append({"text": block.get("text", "")})
                elif btype == "tool_use":
                    parts.append({
                        "function_call": {
                            "name": block.get("name", ""),
                            "args": block.get("input") or {},
                        }
                    })
                elif btype == "tool_result":
                    # tool_result vai como function_response com role=user
                    raw = block.get("content", "")
                    response_obj = (
                        raw if isinstance(raw, dict | list)
                        else {"result": raw if isinstance(raw, str) else str(raw)}
                    )
                    parts.append({
                        "function_response": {
                            "name": block.get("tool_use_id", ""),
                            "response": response_obj,
                        }
                    })
        if parts:
            out.append({"role": gemini_role, "parts": parts})
    return out


@register_chat_provider("google")
class GoogleChatProvider(ChatLLMProvider):
    """ChatLLMProvider implementado sobre `google.genai` (Gemini)."""

    name = "google"

    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key
        self._client: Any | None = None

    def _get_client(self):
        if self._client is None:
            from google import genai  # noqa: PLC0415

            self._client = genai.Client(api_key=self._api_key)
        return self._client

    async def stream_with_tools(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec],
        max_tokens: int = 4096,
        untrusted_messages: bool = False,
    ) -> AsyncIterator[ChatEvent]:
        client = self._get_client()
        contents = _convert_messages_to_gemini(messages)

        # Tools no formato Gemini: Tool(function_declarations=[...])
        from google.genai import types as gtypes  # noqa: PLC0415

        tool_config: list[Any] | None = None
        if tools:
            tool_config = [
                gtypes.Tool(
                    function_declarations=[t.to_gemini_dict() for t in tools]
                )
            ]

        config_kwargs: dict[str, Any] = {
            "max_output_tokens": max_tokens,
        }
        if system:
            config_kwargs["system_instruction"] = system
        if tool_config:
            config_kwargs["tools"] = tool_config

        try:
            stream = await client.aio.models.generate_content_stream(
                model=model,
                contents=contents,
                config=gtypes.GenerateContentConfig(**config_kwargs),
            )

            text_buf = ""
            tool_calls_collected: list[dict[str, Any]] = []
            input_tokens = 0
            output_tokens = 0
            finish_reason = ""

            async for chunk in stream:
                # Usage metadata vem em cada chunk; ultimo eh autoritativo
                usage = getattr(chunk, "usage_metadata", None)
                if usage:
                    input_tokens = getattr(usage, "prompt_token_count", input_tokens)
                    output_tokens = getattr(
                        usage, "candidates_token_count", output_tokens
                    )

                candidates = getattr(chunk, "candidates", None) or []
                for cand in candidates:
                    fr = getattr(cand, "finish_reason", None)
                    if fr:
                        finish_reason = str(fr)
                    parts = getattr(getattr(cand, "content", None), "parts", None) or []
                    for part in parts:
                        # Texto incremental
                        text = getattr(part, "text", None)
                        if text:
                            text_buf += text
                            yield ChatTokenEvent(text=text)
                        # Function call
                        fn_call = getattr(part, "function_call", None)
                        if fn_call and getattr(fn_call, "name", None):
                            tool_calls_collected.append({
                                "name": fn_call.name,
                                "args": dict(getattr(fn_call, "args", {}) or {}),
                            })

            content_blocks: list[Any] = []
            if text_buf:
                content_blocks.append({"type": "text", "text": text_buf})

            for idx, tc in enumerate(tool_calls_collected):
                # Gemini nao retorna IDs estaveis — gerar synthetic id
                tool_id = f"gemini_call_{idx}"
                content_blocks.append({
                    "type": "tool_use",
                    "id": tool_id,
                    "name": tc["name"],
                    "input": tc["args"],
                })
                yield ChatToolUseEvent(
                    id=tool_id,
                    name=tc["name"],
                    input=tc["args"],
                )

            yield ChatEndEvent(
                content_blocks=content_blocks,
                output_tokens=output_tokens,
                input_tokens=input_tokens,
                stop_reason=finish_reason,
            )
        except Exception as exc:  # noqa: BLE001
            yield ChatErrorEvent(
                message=str(exc),
                exception_type=type(exc).__name__,
            )


# Pra evitar warning de import nao usado — json eh usado se precisar serializar
_ = json
