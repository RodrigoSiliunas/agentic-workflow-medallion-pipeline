"""LLM Orchestrator — streaming chat + tool use via observer-framework.

T7 F3+F4:
- Consome `observer.chat.ChatLLMProvider` no lugar de `anthropic.AsyncAnthropic`
  direto. T1 hardening (sanitização XML, redaction) fica disponível sem
  duplicação.
- Tool catalog extraído para `app/services/tools/` — adicionar tool novo
  = 1 arquivo + decorator `@register_tool`. `TOOLS` list e `_execute_tool`
  do antigo orchestrator viraram derivados do registry.
"""

import json
import uuid
from collections.abc import AsyncGenerator

import structlog
from observer.chat import (
    ChatEndEvent,
    ChatErrorEvent,
    ChatLLMProvider,
    ChatTokenEvent,
    ChatToolUseEvent,
    create_chat_provider,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.services.context_engine import ContextEngine
from app.services.credential_service import (
    PROVIDER_CREDENTIAL_MAP,
    CredentialService,
)
from app.services.custom_llm_service import CustomLLMService
from app.services.databricks_service import DatabricksService
from app.services.github_service import GitHubService
from app.services.tools import (
    TOOL_REGISTRY,
    ToolContext,
    all_tool_specs,
)

logger = structlog.get_logger()

MAX_TOOL_ROUNDS = 10


class LLMOrchestrator:
    """Orchestrator multi-provider — provider e model resolvidos dinamicamente.

    Resolucao em ordem de precedencia:
      1. override explicito (model_override + provider_override)
      2. session.preferred_provider/model (per-sessao chat)
      3. channel.preferred_provider/model (per-canal Omni)
      4. company.preferred_provider/model (default empresa)

    Provider valido: "anthropic" | "openai" | "google".
    Model: literal aceito pela API daquele provider (ex: claude-opus-4-7,
    gpt-5, gemini-2.5-pro). Backward compat: aliases curtos
    "sonnet"/"opus"/"haiku" mapeiam pra claude-* atual.
    """

    # Aliases legacy → model IDs atuais. Mantidos pra compat com migrations
    # antigas que setaram preferred_model="sonnet" antes do refactor.
    _LEGACY_MODEL_ALIASES = {
        "sonnet": "claude-sonnet-4-6",
        "opus": "claude-opus-4-7",
        "haiku": "claude-haiku-4-5",
    }

    def __init__(
        self, db: AsyncSession, company_id: uuid.UUID, user_name: str
    ):
        self.db = db
        self.company_id = company_id
        self.user_name = user_name
        self.databricks = DatabricksService(db, company_id)
        self.github = GitHubService(db, company_id)
        self.context_engine = ContextEngine(db, company_id)
        self._cred_service = CredentialService(db)

    async def _get_chat_provider(
        self, provider_override: str | None = None
    ) -> tuple[ChatLLMProvider, str]:
        """Resolve provider name + cria ChatLLMProvider via factory.

        Suporta:
          - "anthropic" | "openai" | "google"  -> built-in (api_key via cred_service)
          - "custom:<uuid>"                    -> CustomLLMEndpoint do DB
        """
        provider_name = provider_override or await self._resolve_company_provider()

        # Custom endpoint (Ollama, vLLM, OpenRouter, etc)
        if provider_name.startswith("custom:"):
            import uuid as _uuid

            endpoint_id = provider_name.removeprefix("custom:")
            try:
                endpoint_uuid = _uuid.UUID(endpoint_id)
            except ValueError as exc:
                raise ValueError(
                    f"Provider 'custom:{endpoint_id}' tem UUID invalido"
                ) from exc

            custom_svc = CustomLLMService(self.db)
            endpoint = await custom_svc.get(self.company_id, endpoint_uuid)
            if not endpoint:
                raise ValueError(
                    f"Custom endpoint {endpoint_id} nao encontrado pra esta empresa"
                )
            if not endpoint.enabled:
                raise ValueError(
                    f"Custom endpoint '{endpoint.name}' esta desabilitado"
                )
            api_key = custom_svc.decrypt_api_key(endpoint)
            return (
                create_chat_provider(
                    "openai-compatible",
                    api_key=api_key,
                    base_url=endpoint.base_url,
                ),
                provider_name,
            )

        # Built-in provider
        cred_type = PROVIDER_CREDENTIAL_MAP.get(provider_name)
        if not cred_type:
            raise ValueError(
                f"Provider '{provider_name}' nao suportado. "
                f"Validos: {list(PROVIDER_CREDENTIAL_MAP.keys())} ou 'custom:<uuid>'"
            )
        api_key = await self._cred_service.get_decrypted(self.company_id, cred_type)
        if not api_key:
            raise ValueError(
                f"API key '{cred_type}' nao configurada — "
                f"abra /settings e preencha pra usar provider '{provider_name}'"
            )
        return create_chat_provider(provider_name, api_key=api_key), provider_name

    async def _resolve_company_provider(self) -> str:
        """Le preferred_provider da empresa, default 'anthropic'."""
        result = await self.db.execute(
            select(Company.preferred_provider).where(Company.id == self.company_id)
        )
        return result.scalar_one_or_none() or "anthropic"

    async def _get_model(self, override: str | None = None) -> str:
        """Resolve model id. Aliases legacy convertidos."""
        if override:
            return self._LEGACY_MODEL_ALIASES.get(override, override)
        result = await self.db.execute(
            select(Company.preferred_model).where(Company.id == self.company_id)
        )
        pref = result.scalar_one_or_none() or "claude-sonnet-4-6"
        return self._LEGACY_MODEL_ALIASES.get(pref, pref)

    def _tool_context(self) -> ToolContext:
        return ToolContext(
            databricks=self.databricks,
            github=self.github,
            company_id=self.company_id,
            user_name=self.user_name,
        )

    async def process_message(
        self,
        user_message: str,
        pipeline_job_id: int,
        conversation_history: list[dict],
        model_override: str | None = None,
        provider_override: str | None = None,
        pipeline_id: uuid.UUID | None = None,
        system_prompt_override: str | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Processa mensagem do usuário. Yields SSE events.

        Resolution order pra provider/model:
          1. provider_override / model_override (caller explicit)
          2. pipeline.preferred_provider/model (per-pipeline runtime)
          3. company.preferred_provider/model (default empresa)
        """
        # Pipeline-level override (so se nao houver explicit)
        if pipeline_id and (not provider_override or not model_override):
            from app.models.pipeline import Pipeline as _Pipeline
            pip_result = await self.db.execute(
                select(_Pipeline).where(
                    _Pipeline.id == pipeline_id,
                    _Pipeline.company_id == self.company_id,
                )
            )
            pip = pip_result.scalar_one_or_none()
            if pip:
                provider_override = provider_override or pip.preferred_provider
                model_override = model_override or pip.preferred_model

        provider, provider_name = await self._get_chat_provider(provider_override)
        model = await self._get_model(model_override)
        logger.info(
            "chat process_message",
            provider=provider_name,
            model=model,
            pipeline_id=str(pipeline_id) if pipeline_id else None,
            company_id=str(self.company_id),
        )

        if system_prompt_override is not None:
            # Modo sem pipeline (ou contexto custom): pula assemble, evita
            # tentar carregar runs/schemas pra job_id=0.
            system = system_prompt_override + "\n\n"
        else:
            context = await self.context_engine.assemble(
                pipeline_job_id=pipeline_job_id,
                user_message=user_message,
            )
            system = context.system_prompt + "\n\n"
            for block in context.blocks:
                system += f"<{block.type}>\n{block.content}\n</{block.type}>\n\n"

        messages = conversation_history + [{"role": "user", "content": user_message}]
        tool_specs = all_tool_specs()

        for _round in range(MAX_TOOL_ROUNDS):
            collected_tool_calls: list[ChatToolUseEvent] = []
            final_content_blocks: list = []
            total_tokens = 0

            async for event in provider.stream_with_tools(
                model=model,
                system=system,
                messages=messages,
                tools=tool_specs,
                max_tokens=4096,
            ):
                if isinstance(event, ChatTokenEvent):
                    yield {"type": "token", "content": event.text}
                elif isinstance(event, ChatToolUseEvent):
                    collected_tool_calls.append(event)
                elif isinstance(event, ChatEndEvent):
                    total_tokens = event.output_tokens
                    final_content_blocks = event.content_blocks
                elif isinstance(event, ChatErrorEvent):
                    logger.error("chat stream error", error=event.message)
                    yield {"type": "error", "content": event.message}
                    return

            if not collected_tool_calls:
                yield {
                    "type": "done",
                    "model": model,
                    "provider": provider_name,
                    "tokens": total_tokens,
                }
                return

            tool_results = []
            for call in collected_tool_calls:
                result = await self._execute_tool(call.name, call.input)
                yield {
                    "type": "action",
                    "action": call.name,
                    "status": "success" if "error" not in result else "failed",
                    "details": result,
                }
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": call.id,
                    "content": json.dumps(result, default=str),
                })

            messages.append({"role": "assistant", "content": final_content_blocks})
            messages.append({"role": "user", "content": tool_results})

        yield {"type": "error", "content": "Limite de rounds de tool use atingido"}

    async def _execute_tool(self, name: str, input_data: dict) -> dict:
        """Executa uma tool via `TOOL_REGISTRY`. Catch-all handler de erros."""
        cls = TOOL_REGISTRY.get(name)
        if cls is None:
            return {"error": f"Tool desconhecida: {name}"}
        try:
            return await cls().run(self._tool_context(), input_data)
        except Exception as exc:  # noqa: BLE001
            logger.error("Tool execution failed", tool=name, error=str(exc))
            return {"error": str(exc)}
