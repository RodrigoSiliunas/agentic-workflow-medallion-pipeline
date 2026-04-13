"""LLM Orchestrator — Claude API com tool use e streaming SSE."""

import json
import uuid
from collections.abc import AsyncGenerator

import anthropic
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.context_engine import ContextEngine
from app.services.credential_service import CredentialService
from app.services.databricks_service import DatabricksService
from app.services.github_service import GitHubService

logger = structlog.get_logger()

MAX_TOOL_ROUNDS = 10

# Tool definitions para Claude API
TOOLS = [
    {
        "name": "list_databricks_jobs",
        "description": "Lista todos os jobs/workflows do Databricks com job_id e nome.",
        "input_schema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 20}},
        },
    },
    {
        "name": "get_job_details",
        "description": "Config completa de um job: schedule, tasks, timeout, tags.",
        "input_schema": {
            "type": "object",
            "properties": {"job_id": {"type": "integer"}},
            "required": ["job_id"],
        },
    },
    {
        "name": "update_job_schedule",
        "description": (
            "Altera cron de um job. REQUER CONFIRMACAO. "
            "Quartz: '0 0 6 * * ?' = diario 6h."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "job_id": {"type": "integer"},
                "cron": {
                    "type": "string",
                    "description": "Quartz cron (ex: '0 0 6 * * ?')",
                },
                "timezone": {"type": "string", "default": "America/Sao_Paulo"},
                "paused": {"type": "boolean", "default": False},
            },
            "required": ["job_id", "cron"],
        },
    },
    {
        "name": "update_job_settings",
        "description": (
            "Atualiza config de um job (timeout, tags). "
            "REQUER CONFIRMACAO."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "job_id": {"type": "integer"},
                "settings": {
                    "type": "object",
                    "description": "Settings a alterar",
                },
            },
            "required": ["job_id", "settings"],
        },
    },
    {
        "name": "get_pipeline_status",
        "description": "Retorna status atual do pipeline (running, idle, failed).",
        "input_schema": {
            "type": "object",
            "properties": {"pipeline_job_id": {"type": "integer"}},
            "required": ["pipeline_job_id"],
        },
    },
    {
        "name": "get_run_logs",
        "description": "Busca logs de uma run especifica do pipeline.",
        "input_schema": {
            "type": "object",
            "properties": {"run_id": {"type": "integer"}},
            "required": ["run_id"],
        },
    },
    {
        "name": "query_delta_table",
        "description": "Executa SELECT SQL em tabelas Delta. Apenas SELECT.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "Query SQL (SELECT only)"},
                "max_rows": {"type": "integer", "default": 50},
            },
            "required": ["sql"],
        },
    },
    {
        "name": "get_table_schema",
        "description": "Retorna schema completo de uma tabela Delta.",
        "input_schema": {
            "type": "object",
            "properties": {"catalog": {"type": "string", "default": "medallion"}},
        },
    },
    {
        "name": "read_file",
        "description": "Le conteudo de um arquivo do repositorio do pipeline.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "ref": {"type": "string", "default": "main"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "list_recent_prs",
        "description": "Lista PRs recentes do repositorio.",
        "input_schema": {
            "type": "object",
            "properties": {
                "state": {"type": "string", "default": "all"},
                "limit": {"type": "integer", "default": 10},
            },
        },
    },
    {
        "name": "get_pr_diff",
        "description": "Mostra o diff de um PR — arquivos alterados e o patch.",
        "input_schema": {
            "type": "object",
            "properties": {"pr_number": {"type": "integer"}},
            "required": ["pr_number"],
        },
    },
    {
        "name": "create_pull_request",
        "description": "Cria PR com mudancas no codigo. REQUER CONFIRMACAO.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "branch": {"type": "string"},
                "files": {
                    "type": "object",
                    "description": "Dict path->content dos arquivos a modificar",
                },
            },
            "required": ["title", "description", "branch"],
        },
    },
    {
        "name": "trigger_pipeline_run",
        "description": "Dispara execucao do pipeline. REQUER CONFIRMACAO.",
        "input_schema": {
            "type": "object",
            "properties": {"pipeline_job_id": {"type": "integer"}},
            "required": ["pipeline_job_id"],
        },
    },
]

CONFIRMATION_REQUIRED = {
    "create_pull_request", "trigger_pipeline_run",
    "update_job_schedule", "update_job_settings",
}


class LLMOrchestrator:
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

    async def _get_anthropic_client(self) -> anthropic.AsyncAnthropic:
        api_key = await self._cred_service.get_decrypted(
            self.company_id, "anthropic_api_key"
        )
        if not api_key:
            raise ValueError("Anthropic API key nao configurada para esta empresa")
        return anthropic.AsyncAnthropic(api_key=api_key)

    MODEL_MAP = {
        "sonnet": "claude-sonnet-4-20250514",
        "opus": "claude-opus-4-20250514",
        "haiku": "claude-haiku-4-5-20251001",
    }

    async def _get_model(self, override: str | None = None) -> str:
        if override and override in self.MODEL_MAP:
            return self.MODEL_MAP[override]
        from sqlalchemy import select

        from app.models.company import Company
        result = await self.db.execute(
            select(Company.preferred_model).where(Company.id == self.company_id)
        )
        pref = result.scalar_one_or_none() or "sonnet"
        return self.MODEL_MAP.get(pref, self.MODEL_MAP["sonnet"])

    async def process_message(
        self,
        user_message: str,
        pipeline_job_id: int,
        conversation_history: list[dict],
        model_override: str | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Processa mensagem do usuario. Yields SSE events."""
        client = await self._get_anthropic_client()
        model = await self._get_model(model_override)

        # Montar contexto
        context = await self.context_engine.assemble(
            pipeline_job_id=pipeline_job_id,
            user_message=user_message,
        )

        # System prompt + contexto
        system = context.system_prompt + "\n\n"
        for block in context.blocks:
            system += f"<{block.type}>\n{block.content}\n</{block.type}>\n\n"

        # Mensagens
        messages = conversation_history + [{"role": "user", "content": user_message}]

        # Loop de tool use com streaming real token-a-token.
        # Cada round: stream texto → coleta tool_use → executa → loop.
        # So a resposta FINAL (sem tool_use) e streamed pro usuario.
        # Rounds intermediarios emitem apenas action events.
        for _round in range(MAX_TOOL_ROUNDS):
            # Stream pra capturar texto + tool calls
            collected_text = ""
            tool_calls = []
            total_tokens = 0

            async with client.messages.stream(
                model=model,
                max_tokens=4096,
                system=system,
                messages=messages,
                tools=TOOLS,
            ) as stream:
                async for event in stream:
                    if event.type == "content_block_delta":
                        if hasattr(event.delta, "text"):
                            collected_text += event.delta.text
                            yield {"type": "token", "content": event.delta.text}
                    elif event.type == "message_delta" and hasattr(event.usage, "output_tokens"):
                        total_tokens = event.usage.output_tokens

                # Extrair tool calls da mensagem final (mais confiavel que streaming parcial)
                final_message = await stream.get_final_message()
                tool_calls = [
                    block for block in final_message.content
                    if block.type == "tool_use"
                ]

            # Se nao tem tool calls, resposta finalizada
            if not tool_calls:
                yield {"type": "done", "model": model, "tokens": total_tokens}
                return

            # Executar tools
            tool_results = []
            for call in tool_calls:
                # Verificar se precisa confirmacao
                if call.name in CONFIRMATION_REQUIRED:
                    yield {
                        "type": "action",
                        "action": "confirmation_required",
                        "tool": call.name,
                        "input": call.input,
                        "details": {"tool_id": call.id},
                    }
                    # Nao executar — retornar pedido de confirmacao ao LLM
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": call.id,
                        "content": json.dumps({
                            "status": "awaiting_confirmation",
                            "message": "O usuario precisa confirmar esta acao. "
                                       "Pergunte ao usuario se deseja prosseguir e "
                                       "descreva exatamente o que sera feito.",
                        }),
                    })
                    continue

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

            # Adicionar tool calls + results e continuar loop
            messages.append({"role": "assistant", "content": final_message.content})
            messages.append({"role": "user", "content": tool_results})

        yield {"type": "error", "content": "Limite de rounds de tool use atingido"}

    async def _execute_tool(self, name: str, input_data: dict) -> dict:
        """Executa uma tool e retorna resultado."""
        try:
            if name == "list_databricks_jobs":
                return {
                    "jobs": await self.databricks.list_jobs(
                        input_data.get("limit", 20)
                    )
                }

            if name == "get_job_details":
                return await self.databricks.get_job_details(input_data["job_id"])

            if name == "update_job_schedule":
                return await self.databricks.update_job_schedule(
                    job_id=input_data["job_id"],
                    cron=input_data["cron"],
                    timezone=input_data.get("timezone", "America/Sao_Paulo"),
                    paused=input_data.get("paused", False),
                )

            if name == "update_job_settings":
                return await self.databricks.update_job_settings(
                    job_id=input_data["job_id"],
                    settings=input_data["settings"],
                )

            if name == "get_pipeline_status":
                return await self.databricks.get_pipeline_summary(
                    input_data["pipeline_job_id"]
                )

            if name == "get_run_logs":
                return await self.databricks.get_run_output(input_data["run_id"])

            if name == "query_delta_table":
                sql = input_data["sql"].strip()
                sql_upper = sql.upper()
                # Guard: somente SELECT puro, sem multi-statement ou DDL
                forbidden = {
                    "INSERT", "UPDATE", "DELETE", "DROP", "CREATE",
                    "ALTER", "TRUNCATE", "EXEC", "GRANT", "REVOKE",
                }
                if not sql_upper.startswith("SELECT"):
                    return {"error": "Apenas queries SELECT sao permitidas"}
                if ";" in sql:
                    return {"error": "Multi-statement nao permitido"}
                tokens = set(sql_upper.split())
                if tokens & forbidden:
                    return {"error": f"Palavras proibidas detectadas: {tokens & forbidden}"}
                return await self.databricks.query_table(
                    sql, input_data.get("max_rows", 50)
                )

            if name == "get_table_schema":
                return {
                    "schemas": await self.databricks.get_table_schemas(
                        input_data.get("catalog", "medallion")
                    )
                }

            if name == "read_file":
                content = await self.github.read_file(
                    input_data["path"], input_data.get("ref", "main")
                )
                return {"path": input_data["path"], "content": content}

            if name == "list_recent_prs":
                return {
                    "prs": await self.github.list_recent_prs(
                        input_data.get("state", "all"),
                        input_data.get("limit", 10),
                    )
                }

            if name == "get_pr_diff":
                return await self.github.get_pr_diff(input_data["pr_number"])

            if name == "create_pull_request":
                branch = f"feat/{self.user_name}/{input_data['branch']}"
                return await self.github.create_pr(
                    title=input_data["title"],
                    body=input_data["description"],
                    branch=branch,
                    files=input_data.get("files"),
                )

            if name == "trigger_pipeline_run":
                return await self.databricks.trigger_run(
                    input_data["pipeline_job_id"]
                )

            return {"error": f"Tool desconhecida: {name}"}

        except Exception as e:
            logger.error("Tool execution failed", tool=name, error=str(e))
            return {"error": str(e)}
