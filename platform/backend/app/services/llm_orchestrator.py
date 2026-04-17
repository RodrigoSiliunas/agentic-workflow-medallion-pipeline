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
from app.services.credential_service import CredentialService
from app.services.databricks_service import DatabricksService
from app.services.github_service import GitHubService
from app.services.tools import (
    TOOL_REGISTRY,
    ToolContext,
    all_tool_specs,
    confirmation_required_tools,
)

logger = structlog.get_logger()

MAX_TOOL_ROUNDS = 10

# Retrocompat — código legado pode importar `TOOLS` e `CONFIRMATION_REQUIRED`.
# Fonte de verdade agora é `TOOL_REGISTRY`.
TOOLS = [spec.to_anthropic_dict() for spec in all_tool_specs()]
CONFIRMATION_REQUIRED = confirmation_required_tools()


class LLMOrchestrator:
    MODEL_MAP = {
        "sonnet": "claude-sonnet-4-20250514",
        "opus": "claude-opus-4-20250514",
        "haiku": "claude-haiku-4-5-20251001",
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

    async def _get_chat_provider(self) -> ChatLLMProvider:
        api_key = await self._cred_service.get_decrypted(
            self.company_id, "anthropic_api_key"
        )
        if not api_key:
            raise ValueError("Anthropic API key nao configurada para esta empresa")
        return create_chat_provider("anthropic", api_key=api_key)

    async def _get_model(self, override: str | None = None) -> str:
        if override and override in self.MODEL_MAP:
            return self.MODEL_MAP[override]
        result = await self.db.execute(
            select(Company.preferred_model).where(Company.id == self.company_id)
        )
        pref = result.scalar_one_or_none() or "sonnet"
        return self.MODEL_MAP.get(pref, self.MODEL_MAP["sonnet"])

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
    ) -> AsyncGenerator[dict, None]:
        """Processa mensagem do usuário. Yields SSE events."""
        provider = await self._get_chat_provider()
        model = await self._get_model(model_override)

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
                yield {"type": "done", "model": model, "tokens": total_tokens}
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
