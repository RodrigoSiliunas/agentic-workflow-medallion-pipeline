"""OpenAICompatibleChatProvider — generico pra Ollama, vLLM, LM Studio, LocalAI.

Reusa 100% do OpenAIChatProvider — diferenca eh apenas que aceita
`base_url` custom + `api_key` opcional (Ollama nao valida, dummy "ollama"
serve). Permite multi-tenant com varios endpoints simultaneos.

Tagged como provider separado pra UI conseguir distinguir "OpenAI cloud"
de "self-hosted compativel". Mas a logica eh a mesma.
"""

from __future__ import annotations

from observer.chat.openai import OpenAIChatProvider
from observer.chat.registry import register_chat_provider


@register_chat_provider("openai-compatible")
class OpenAICompatibleChatProvider(OpenAIChatProvider):
    """Generico pra qualquer endpoint OpenAI-compatible (Ollama, vLLM, etc).

    Configuracao:
        provider = create_chat_provider(
            "openai-compatible",
            api_key="ollama",                          # dummy ok
            base_url="http://ollama:11434/v1",
        )

    Tools, streaming, JSON mode — tudo herda do OpenAIChatProvider.
    Ollama implementa OpenAI Chat Completions API desde 0.1.34+.
    """

    name = "openai-compatible"

    def __init__(self, api_key: str = "ollama", base_url: str | None = None) -> None:
        # api_key default "ollama" cobre Ollama (que ignora). vLLM/LocalAI
        # tambem aceitam dummy. Quem realmente exige (OpenRouter, Together)
        # caller passa via kwargs.
        super().__init__(api_key=api_key or "ollama", base_url=base_url)
