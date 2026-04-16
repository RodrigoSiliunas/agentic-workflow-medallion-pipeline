"""AnthropicChatProvider — streaming + tool use via `anthropic.AsyncAnthropic`.

Implementação do `ChatLLMProvider` protocol. Recebe lista de mensagens +
tools, retorna AsyncIterator de `ChatEvent`. Cada delta do stream vira
`ChatTokenEvent`; tool_use blocks na mensagem final viram
`ChatToolUseEvent`; fim do round vira `ChatEndEvent`.

Reusa `_sanitize_for_xml_tag` quando `untrusted_messages=True`.
"""

from __future__ import annotations

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
from observer.providers.anthropic_provider import _sanitize_for_xml_tag


def _sanitize_user_content(content: Any) -> Any:
    """Aplica sanitização XML em strings dentro de `content`.

    `content` pode ser string ou lista de blocks (como no Anthropic SDK).
    Apenas texto user-facing é sanitizado; blocks `tool_result` passam
    intactos.
    """
    if isinstance(content, str):
        return _sanitize_for_xml_tag(content, "user_message")
    if isinstance(content, list):
        sanitized = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text", "")
                sanitized.append(
                    {**block, "text": _sanitize_for_xml_tag(text, "user_message")}
                )
            else:
                sanitized.append(block)
        return sanitized
    return content


def _maybe_sanitize_messages(
    messages: list[dict[str, Any]], untrusted: bool
) -> list[dict[str, Any]]:
    if not untrusted:
        return messages
    out: list[dict[str, Any]] = []
    for msg in messages:
        if msg.get("role") == "user":
            out.append({**msg, "content": _sanitize_user_content(msg.get("content", ""))})
        else:
            out.append(msg)
    return out


@register_chat_provider("anthropic")
class AnthropicChatProvider(ChatLLMProvider):
    """ChatLLMProvider implementado sobre `anthropic.AsyncAnthropic`."""

    name = "anthropic"

    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key
        self._client: Any | None = None

    def _get_client(self):
        # Import tardio — `anthropic` é optional dep
        if self._client is None:
            import anthropic  # noqa: PLC0415

            self._client = anthropic.AsyncAnthropic(api_key=self._api_key)
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
        prepared_messages = _maybe_sanitize_messages(messages, untrusted_messages)
        tools_payload = [t.to_anthropic_dict() for t in tools]

        try:
            async with client.messages.stream(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=prepared_messages,
                tools=tools_payload,
            ) as stream:
                output_tokens = 0
                input_tokens = 0
                async for event in stream:
                    etype = getattr(event, "type", None)
                    if etype == "content_block_delta":
                        delta = getattr(event, "delta", None)
                        if delta is not None and hasattr(delta, "text"):
                            yield ChatTokenEvent(text=delta.text)
                    elif etype == "message_delta":
                        usage = getattr(event, "usage", None)
                        if usage is not None and hasattr(usage, "output_tokens"):
                            output_tokens = usage.output_tokens

                final = await stream.get_final_message()

            # Mensagem final — extrai tool_use blocks + totaliza usage
            content_blocks = list(final.content)
            final_usage = getattr(final, "usage", None)
            if final_usage is not None:
                input_tokens = getattr(final_usage, "input_tokens", 0)
                output_tokens = getattr(final_usage, "output_tokens", output_tokens)
            stop_reason = getattr(final, "stop_reason", "") or ""

            for block in content_blocks:
                if getattr(block, "type", None) == "tool_use":
                    yield ChatToolUseEvent(
                        id=block.id,
                        name=block.name,
                        input=dict(block.input) if block.input else {},
                    )

            yield ChatEndEvent(
                content_blocks=content_blocks,
                output_tokens=output_tokens,
                input_tokens=input_tokens,
                stop_reason=stop_reason,
            )
        except Exception as exc:  # noqa: BLE001
            yield ChatErrorEvent(
                message=str(exc),
                exception_type=type(exc).__name__,
            )
