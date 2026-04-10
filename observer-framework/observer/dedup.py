"""Deduplicacao de diagnosticos do Observer.

Antes de chamar o LLM, verifica se o mesmo erro ja foi diagnosticado
recentemente na tabela `observer.diagnostics`. Se ja existe um diagnostico
bem-sucedido dentro da janela de dedup e o PR ainda esta aberto ou foi
mergeado, pula o novo diagnostico (evita PRs duplicados e gasto de tokens).

Se o PR anterior foi fechado sem merge, permite re-diagnostico (o fix nao
foi aceito, entao novo diagnostico eh bem-vindo).

Uso:
    from observer import check_duplicate

    result = check_duplicate(
        store=store,
        error_message=ctx["error_message"],
        window_hours=24,
        git_provider=git,
    )
    if result.is_duplicate:
        log.append(f"Cache HIT: {result.reason}")
        continue
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from observer.persistence import (
    ObserverDiagnosticsStore,
    error_hash,
)

logger = logging.getLogger(__name__)


@dataclass
class DuplicateCheckResult:
    """Resultado da verificacao de duplicidade.

    is_duplicate: True se o Observer deve pular o diagnostico.
    reason: motivo textual da decisao, para logs e observabilidade.
    existing_record: dict com os campos do diagnostico anterior quando houver,
        contendo ao menos id, timestamp, pr_url, pr_number, branch_name.
    """

    is_duplicate: bool
    reason: str
    existing_record: dict[str, Any] | None = None


def check_duplicate(
    store: ObserverDiagnosticsStore,
    error_message: str,
    *,
    window_hours: int = 24,
    git_provider: Any | None = None,
) -> DuplicateCheckResult:
    """Verifica se um erro ja foi diagnosticado recentemente com sucesso.

    Fluxo de decisao:
      1. Calcula SHA-256 do error_message (via `error_hash`).
      2. Busca diagnosticos na tabela com o mesmo hash, status='success'
         e dentro da janela de `window_hours`.
      3. Se nao encontrou: cache miss -> is_duplicate=False
      4. Se encontrou e nao ha git_provider: safe default -> is_duplicate=True
      5. Se encontrou e ha git_provider:
         - PR open/merged: skip -> is_duplicate=True
         - PR closed (sem merge): re-diagnosticar -> is_duplicate=False
         - status unknown ou exception: safe default -> is_duplicate=True
    """
    try:
        ehash = error_hash(error_message)
        existing = store.find_recent_successful(
            error_hash_value=ehash,
            window_hours=window_hours,
        )
    except Exception as exc:
        # Em caso de erro na consulta (tabela ainda nao existe, conexao falha etc)
        # permitimos o diagnostico para nao bloquear o Observer
        logger.warning(f"Dedup query falhou, permitindo diagnostico: {exc}")
        return DuplicateCheckResult(
            is_duplicate=False,
            reason="dedup_query_failed",
        )

    if not existing:
        return DuplicateCheckResult(
            is_duplicate=False,
            reason="no_previous_success",
        )

    # Mais recente primeiro (find_recent_successful ja faz ORDER BY desc)
    record = existing[0]
    pr_number = int(record.get("pr_number") or 0)

    # Sem git_provider: safe default — assume que o diagnostico anterior ainda eh valido
    if git_provider is None:
        return DuplicateCheckResult(
            is_duplicate=True,
            reason="previous_success_no_git_check",
            existing_record=record,
        )

    # Sem pr_number: nao ha como consultar, safe default
    if not pr_number:
        return DuplicateCheckResult(
            is_duplicate=True,
            reason="previous_success_without_pr_number",
            existing_record=record,
        )

    try:
        pr_status = git_provider.get_pr_status(pr_number)
    except Exception as exc:
        logger.warning(f"get_pr_status falhou para PR #{pr_number}: {exc}")
        return DuplicateCheckResult(
            is_duplicate=True,
            reason="pr_status_check_failed",
            existing_record=record,
        )

    if pr_status in ("open", "merged"):
        return DuplicateCheckResult(
            is_duplicate=True,
            reason=f"previous_pr_{pr_status}",
            existing_record=record,
        )

    if pr_status == "closed":
        # PR fechado sem merge — fix anterior foi rejeitado, permite re-diagnostico
        return DuplicateCheckResult(
            is_duplicate=False,
            reason="previous_pr_closed_without_merge",
            existing_record=record,
        )

    # 'unknown' ou qualquer outro estado — safe default
    return DuplicateCheckResult(
        is_duplicate=True,
        reason=f"previous_pr_status_{pr_status}",
        existing_record=record,
    )
