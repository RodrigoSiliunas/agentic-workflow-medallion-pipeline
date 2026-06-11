"""Agente NL do Pipeline Editor — separado do LLMOrchestrator.

Converte mensagem natural + draft/manifest Silver em EditProposal estruturado.
Usa observer.chat providers; fallback deterministico se LLM indisponivel.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import structlog
from observer.chat import (
    ChatEndEvent,
    ChatErrorEvent,
    ChatTokenEvent,
    ToolSpec,
    create_chat_provider,
)
from observer.chat.base import ChatToolUseEvent
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.company import Company
from app.services.credential_service import PROVIDER_CREDENTIAL_MAP, CredentialService
from app.services.pipeline_editor.agent import build_edit_proposal
from app.services.pipeline_editor.manifest import (
    PipelineManifest,
    correct_to_last_writer,
    silver_nodes,
)
from app.services.pipeline_editor.schemas import EditProposal, TransformDraft

logger = structlog.get_logger()

def _build_submit_tool(manifest: PipelineManifest) -> ToolSpec:
    """Constrói o tool spec com enum dinâmico dos nós Silver disponíveis.

    Forçar `target_node` a um dos IDs do manifest impede o LLM de inventar
    nomes ou divergir entre a explanation e o draft (bug observado: explicação
    dizia silver_entities mas target_node vinha como silver_dedup).
    """
    silver_ids = [node.id for node in silver_nodes(manifest)]
    return ToolSpec(
        name="submit_edit_proposal",
        description=(
            "Envia proposta estruturada de edicao Silver. "
            "Use apenas operacoes suportadas pelo DSL."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "explanation": {"type": "string"},
                "draft": {
                    "type": "object",
                    "properties": {
                        "layer": {"type": "string", "enum": ["silver"]},
                        "target_node": {"type": "string", "enum": silver_ids},
                        "target_table": {"type": "string"},
                        "operations": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "op": {"type": "string"},
                                    "column": {"type": "string"},
                                    "new_name": {"type": "string"},
                                    "data_type": {"type": "string"},
                                    "pattern": {"type": "string"},
                                    "replacement": {"type": "string"},
                                    "expression": {"type": "string"},
                                    "format": {"type": "string"},
                                    "json_path": {"type": "string"},
                                    "source_columns": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                },
                                "required": ["op"],
                            },
                        },
                        "warnings": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["layer", "target_node", "target_table", "operations"],
                },
                "risk_score": {"type": "integer", "minimum": 0, "maximum": 10},
                "test_plan": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["explanation", "draft"],
        },
    )


def _system_prompt(manifest: PipelineManifest) -> str:
    nodes = silver_nodes(manifest)
    node_lines = "\n".join(
        f"- {node.id}: tabela={node.output_tables[0] if node.output_tables else 'n/a'}"
        for node in nodes
    )
    return (
        "Voce e o agente do Pipeline Editor (camada Silver apenas).\n"
        "Converta pedidos em TransformDraft declarativo.\n"
        "Nao edite arquivos livremente; use submit_edit_proposal.\n"
        "Operacoes validas: drop_column, rename_column, cast_column, trim, "
        "regex_replace, coalesce, derive_column, filter_rows, date_format, "
        "json_extract, mask_pii.\n"
        "Para filter_rows e derive_column use SQL Spark (sem F.col) no preview.\n"
        "Se faltar contexto, explique no campo explanation e envie draft parcial.\n"
        "REGRA CRITICA: quando mais de um node escreve a MESMA tabela, escolha "
        "SEMPRE o ULTIMO escritor — e ele que determina o schema final; aplicar "
        "num escritor anterior vira no-op (o overwrite posterior apaga o efeito).\n"
        f"Nos Silver disponiveis:\n{node_lines or '- nenhum'}"
    )


def _manifest_context(manifest: PipelineManifest) -> str:
    payload = {
        "template_slug": manifest.template_slug,
        "nodes": [
            {
                "id": node.id,
                "task_key": node.task_key,
                "output_tables": node.output_tables,
                "supported_operations": node.supported_operations,
            }
            for node in silver_nodes(manifest)
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


async def _resolve_provider(
    db: AsyncSession,
    company_id: uuid.UUID,
) -> tuple[Any, str]:
    result = await db.execute(
        select(Company.preferred_provider, Company.preferred_model).where(
            Company.id == company_id
        )
    )
    row = result.first()
    provider_name = (row[0] if row else None) or "anthropic"
    model = (row[1] if row else None) or "claude-sonnet-4-6"
    legacy = {
        "sonnet": "claude-sonnet-4-6",
        "opus": "claude-opus-4-7",
        "haiku": "claude-haiku-4-5",
    }
    model = legacy.get(model, model)

    cred_type = PROVIDER_CREDENTIAL_MAP.get(provider_name)
    if not cred_type:
        raise ValueError(f"Provider '{provider_name}' nao suportado pelo Pipeline Editor")

    cred_service = CredentialService(db)
    api_key = await cred_service.get_decrypted(company_id, cred_type)
    if not api_key:
        raise ValueError(f"Credencial {cred_type} nao configurada")

    return create_chat_provider(provider_name, api_key=api_key), model


def _proposal_from_tool_input(
    tool_input: dict[str, Any],
    manifest: PipelineManifest,
) -> EditProposal:
    draft = TransformDraft.model_validate(tool_input["draft"])
    if draft.layer != "silver":
        raise ValueError("Somente camada Silver e suportada")
    node = manifest.resolve_node(draft.target_node)
    if node.layer != "silver":
        raise ValueError(f"No `{draft.target_node}` nao e Silver")

    # Correcao deterministica ao ultimo escritor (helper compartilhado com o
    # approve) — achado nos E2E reais #132/#138: rename aplicado num escritor
    # anterior vira no-op silencioso.
    draft, node = correct_to_last_writer(draft, manifest)
    files = [node.file_path]
    risk = int(tool_input.get("risk_score", 3))
    test_plan = tool_input.get("test_plan") or [
        "Validar DSL e codegen.",
        "Executar preview SQL tenant-scoped.",
        "Criar PR apos aprovacao humana.",
    ]
    return EditProposal(
        explanation=str(tool_input.get("explanation", "")),
        draft=draft,
        files_affected=files,
        risk_score=max(0, min(10, risk)),
        test_plan=list(test_plan),
    )


async def _collect_tool_proposal(
    provider: Any,
    model: str,
    *,
    system: str,
    user_content: str,
    manifest: PipelineManifest,
) -> EditProposal:
    messages = [{"role": "user", "content": user_content}]
    tool_input: dict[str, Any] | None = None
    text_chunks: list[str] = []

    async for event in provider.stream_with_tools(
        model=model,
        system=system,
        messages=messages,
        tools=[_build_submit_tool(manifest)],
        max_tokens=4096,
        untrusted_messages=True,
    ):
        if isinstance(event, ChatTokenEvent):
            text_chunks.append(event.text)
        elif isinstance(event, ChatToolUseEvent):
            if event.name == "submit_edit_proposal":
                tool_input = dict(event.input)
        elif isinstance(event, ChatErrorEvent):
            raise RuntimeError(event.message)
        elif isinstance(event, ChatEndEvent):
            break

    if tool_input:
        return _proposal_from_tool_input(tool_input, manifest)

    joined = "".join(text_chunks).strip()
    if joined.startswith("{"):
        payload = json.loads(joined)
        if "draft" in payload:
            return _proposal_from_tool_input(payload, manifest)

    raise RuntimeError("LLM nao retornou proposta estruturada")


async def build_edit_proposal_from_nl(
    *,
    db: AsyncSession,
    company_id: uuid.UUID,
    user_message: str,
    draft: TransformDraft | None,
    manifest: PipelineManifest,
) -> EditProposal:
    """Gera EditProposal via LLM ou fallback deterministico."""
    if not settings.PIPELINE_EDITOR_LLM_ENABLED:
        return build_edit_proposal(
            user_message=user_message,
            draft=draft,
            manifest=manifest,
        )

    user_content = (
        f"Mensagem do usuario:\n{user_message}\n\n"
        f"Draft atual:\n{draft.model_dump(mode='json') if draft else 'null'}\n\n"
        f"Manifest Silver:\n{_manifest_context(manifest)}"
    )

    try:
        provider, model = await _resolve_provider(db, company_id)
        return await _collect_tool_proposal(
            provider,
            model,
            system=_system_prompt(manifest),
            user_content=user_content,
            manifest=manifest,
        )
    except Exception as exc:
        logger.warning("pipeline_editor_nl_agent_fallback", error=str(exc))
        fallback = build_edit_proposal(
            user_message=user_message,
            draft=draft,
            manifest=manifest,
        )
        fallback.explanation = (
            f"{fallback.explanation}\n\n"
            f"(Fallback deterministico: LLM indisponivel — {exc})"
        )
        return fallback
