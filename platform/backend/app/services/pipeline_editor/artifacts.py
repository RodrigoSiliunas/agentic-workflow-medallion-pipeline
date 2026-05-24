"""Artefatos portáteis do Pipeline Editor."""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from app.services.pipeline_editor.schemas import TransformDraft

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]+"),
    re.compile(r"ghp_[A-Za-z0-9_]+"),
    re.compile(r"AKIA[0-9A-Z]{12,}"),
]


def redact_sensitive_text(text: str) -> str:
    redacted = text
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def build_prompt_markdown(
    *,
    session_id: uuid.UUID,
    pipeline_name: str,
    user_request: str,
    draft: TransformDraft,
    validation: dict[str, Any] | None = None,
    preview: dict[str, Any] | None = None,
) -> str:
    """Gera prompt.md para validar a proposta em outro LLM/chat."""
    request = redact_sensitive_text(user_request)
    operations = [
        operation.model_dump(exclude_none=True)
        for operation in draft.operations
    ]
    sections = [
        "# Pipeline Editor Prompt",
        "",
        "## Contexto",
        f"- Session ID: `{session_id}`",
        f"- Pipeline: {pipeline_name}",
        f"- Layer: `{draft.layer}`",
        f"- Target node: `{draft.target_node}`",
        f"- Target table: `{draft.target_table}`",
        "",
        "## Pedido Original",
        request,
        "",
        "## Operacoes Propostas",
        "```json",
        json.dumps(operations, indent=2, ensure_ascii=False),
        "```",
    ]
    if validation is not None:
        sections.extend([
            "",
            "## Validacao",
            "```json",
            json.dumps(validation, indent=2, ensure_ascii=False, default=str),
            "```",
        ])
    if preview is not None:
        sections.extend([
            "",
            "## Preview",
            "```json",
            json.dumps(preview, indent=2, ensure_ascii=False, default=str),
            "```",
        ])
    sections.extend([
        "",
        "## Instrucoes para Revisao",
        "Avalie se as operacoes preservam o contrato do pipeline, nao expõem PII e "
        "mantêm isolamento do tenant.",
    ])
    return "\n".join(sections) + "\n"
