"""OpenAIChatProvider — streaming + tool use via `openai.AsyncOpenAI`.

Implementa `ChatLLMProvider` protocol pro provider OpenAI (GPT-5, GPT-5
Mini, GPT-4o). Emite mesmo set de `ChatEvent` que o AnthropicChatProvider
(token/tool_use/end/error) — orchestrator nao precisa saber qual SDK roda.

Tools: usa Chat Completions API com `tools=[{"type":"function",...}]`.
Streaming: SSE chunks, deltas vem em `choices[0].delta.content` (texto)
ou `choices[0].delta.tool_calls[0].function.arguments` (tool args parciais).
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


def _convert_messages_anthropic_to_openai(
    messages: list[dict[str, Any]], system: str
) -> list[dict[str, Any]]:
    """Converte historico Anthropic-style pra OpenAI Chat Completions.

    Anthropic: messages = [{"role": "user|assistant", "content": str | [blocks]}]
    OpenAI:    messages = [{"role": "system|user|assistant|tool", "content": str},
                           {"role":"assistant","tool_calls":[...]}]
    """
    out: list[dict[str, Any]] = []
    if system:
        out.append({"role": "system", "content": system})

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        # Conteudo string simples
        if isinstance(content, str):
            out.append({"role": role, "content": content})
            continue

        # Lista de blocks (Anthropic format)
        if isinstance(content, list):
            text_parts: list[str] = []
            tool_calls: list[dict[str, Any]] = []
            tool_results: list[dict[str, Any]] = []
            for block in content:
                if not isinstance(block, dict):
                    # Anthropic SDK objects — extract via getattr
                    btype = getattr(block, "type", None)
                    if btype == "text":
                        text_parts.append(getattr(block, "text", ""))
                    elif btype == "tool_use":
                        tool_calls.append({
                            "id": getattr(block, "id", ""),
                            "type": "function",
                            "function": {
                                "name": getattr(block, "name", ""),
                                "arguments": json.dumps(
                                    dict(getattr(block, "input", {}) or {})
                                ),
                            },
                        })
                    continue
                btype = block.get("type")
                if btype == "text":
                    text_parts.append(block.get("text", ""))
                elif btype == "tool_use":
                    tool_calls.append({
                        "id": block.get("id", ""),
                        "type": "function",
                        "function": {
                            "name": block.get("name", ""),
                            "arguments": json.dumps(block.get("input") or {}),
                        },
                    })
                elif btype == "tool_result":
                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": block.get("tool_use_id", ""),
                        "content": (
                            block.get("content", "")
                            if isinstance(block.get("content"), str)
                            else json.dumps(block.get("content"))
                        ),
                    })

            # Assistant turn com text + tool_calls
            if role == "assistant":
                assistant_msg: dict[str, Any] = {"role": "assistant"}
                if text_parts:
                    assistant_msg["content"] = "".join(text_parts)
                if tool_calls:
                    assistant_msg["tool_calls"] = tool_calls
                if "content" not in assistant_msg and "tool_calls" not in assistant_msg:
                    assistant_msg["content"] = ""
                out.append(assistant_msg)
            else:
                # User turn — text + tool_results vao em mensagens separadas
                if text_parts:
                    out.append({"role": "user", "content": "".join(text_parts)})
                out.extend(tool_results)
    return out


@register_chat_provider("openai")
class OpenAIChatProvider(ChatLLMProvider):
    """ChatLLMProvider implementado sobre `openai.AsyncOpenAI`."""

    name = "openai"

    def __init__(self, api_key: str = "", base_url: str | None = None) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._client: Any | None = None

    def _get_client(self):
        if self._client is None:
            import openai  # noqa: PLC0415

            kwargs: dict[str, Any] = {"api_key": self._api_key}
            if self._base_url:
                kwargs["base_url"] = self._base_url
            self._client = openai.AsyncOpenAI(**kwargs)
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
        prepared = _convert_messages_anthropic_to_openai(messages, system)
        tools_payload = [t.to_openai_dict() for t in tools] or None

        try:
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": prepared,
                "max_tokens": max_tokens,
                "stream": True,
                "stream_options": {"include_usage": True},
            }
            if tools_payload:
                kwargs["tools"] = tools_payload

            stream = await client.chat.completions.create(**kwargs)

            # Acumuladores
            text_buf = ""
            # tool_calls: indexado por slot (OpenAI sends partial args incrementally)
            tool_calls_buf: dict[int, dict[str, Any]] = {}
            input_tokens = 0
            output_tokens = 0
            finish_reason = ""

            async for chunk in stream:
                # Usage chunk vem ao final (stream_options=include_usage)
                if getattr(chunk, "usage", None):
                    usage = chunk.usage
                    input_tokens = getattr(usage, "prompt_tokens", 0)
                    output_tokens = getattr(usage, "completion_tokens", 0)
                if not chunk.choices:
                    continue

                choice = chunk.choices[0]
                delta = choice.delta
                if choice.finish_reason:
                    finish_reason = choice.finish_reason

                # Token de texto
                token_text = getattr(delta, "content", None)
                if token_text:
                    text_buf += token_text
                    yield ChatTokenEvent(text=token_text)

                # Tool call deltas (parciais — args chegam em chunks)
                tool_deltas = getattr(delta, "tool_calls", None) or []
                for td in tool_deltas:
                    idx = td.index
                    slot = tool_calls_buf.setdefault(idx, {
                        "id": "", "name": "", "arguments": ""
                    })
                    if td.id:
                        slot["id"] = td.id
                    fn = getattr(td, "function", None)
                    if fn:
                        if getattr(fn, "name", None):
                            slot["name"] = fn.name
                        if getattr(fn, "arguments", None):
                            slot["arguments"] += fn.arguments

            # Emit tool_use events (consolidados)
            content_blocks: list[Any] = []
            if text_buf:
                content_blocks.append({"type": "text", "text": text_buf})
            for slot in tool_calls_buf.values():
                if not slot.get("name"):
                    continue
                try:
                    parsed_input = json.loads(slot["arguments"] or "{}")
                except json.JSONDecodeError:
                    parsed_input = {"_raw": slot["arguments"]}
                content_blocks.append({
                    "type": "tool_use",
                    "id": slot["id"],
                    "name": slot["name"],
                    "input": parsed_input,
                })
                yield ChatToolUseEvent(
                    id=slot["id"],
                    name=slot["name"],
                    input=parsed_input,
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
