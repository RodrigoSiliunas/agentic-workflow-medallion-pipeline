"""Tipos e protocol do `observer.chat` — streaming chat com tool use.

Paralelo ao `observer.providers.LLMProvider.diagnose()` (single-shot,
sync). Aqui o contrato é async iterator de `ChatEvent`, permitindo
streaming token-a-token + tool use loop.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol


@dataclass(frozen=True)
class ToolSpec:
    """Descritor de ferramenta no formato que o Anthropic API espera.

    `input_schema` é JSON Schema que o LLM usa pra montar inputs.
    """

    name: str
    description: str
    input_schema: dict[str, Any]

    def to_anthropic_dict(self) -> dict[str, Any]:
        """Formato que entra em `messages.stream(tools=[...])`."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }

    def to_openai_dict(self) -> dict[str, Any]:
        """Formato OpenAI Responses/Chat Completions tools[]."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }

    def to_gemini_dict(self) -> dict[str, Any]:
        """Formato Google google-genai FunctionDeclaration."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.input_schema,
        }


# ---------------------------------------------------------------------------
# ChatEvent — tagged union dos eventos emitidos pelo stream
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChatTokenEvent:
    """Pedaço de texto que saiu do modelo neste delta."""

    text: str
    type: Literal["token"] = "token"


@dataclass(frozen=True)
class ChatToolUseEvent:
    """Modelo pediu uma ferramenta — consumidor deve executar e mandar result."""

    id: str
    name: str
    input: dict[str, Any]
    type: Literal["tool_use"] = "tool_use"


@dataclass(frozen=True)
class ChatEndEvent:
    """Fim do round. `content_blocks` vai para `messages[].content` do
    próximo round (assistant message com tool_use blocks inclusos).
    """

    content_blocks: list[Any] = field(default_factory=list)
    output_tokens: int = 0
    input_tokens: int = 0
    stop_reason: str = ""
    type: Literal["end"] = "end"


@dataclass(frozen=True)
class ChatErrorEvent:
    """Erro irrecuperável durante o stream (após retries)."""

    message: str
    exception_type: str = ""
    type: Literal["error"] = "error"


ChatEvent = ChatTokenEvent | ChatToolUseEvent | ChatEndEvent | ChatErrorEvent


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class ChatLLMProvider(Protocol):
    """Contrato pra LLM chat com streaming + tool use.

    Implementações: `AnthropicChatProvider`. Factory: `create_chat_provider`.
    """

    name: str

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
        """Yield `ChatEvent`s enquanto o modelo responde.

        Args:
            model: ID completo do modelo (ex: `claude-sonnet-4-20250514`).
            system: system prompt.
            messages: histórico no formato Anthropic (role + content).
            tools: lista de `ToolSpec` disponíveis nesta round.
            max_tokens: limite de tokens por resposta.
            untrusted_messages: se True, aplica `_sanitize_for_xml_tag`
                no conteúdo de messages com role=user antes do send.
                Útil quando algum content vem de fonte hostil (ex: texto
                de usuário final passando por LLM que pode virar prompt
                injection). Default False.

        Yields:
            `ChatTokenEvent` por delta de texto, `ChatToolUseEvent` ao
            final do stream para cada tool_use block, `ChatEndEvent` no
            final. Em erro fatal pós-retry, `ChatErrorEvent`.
        """
        ...
