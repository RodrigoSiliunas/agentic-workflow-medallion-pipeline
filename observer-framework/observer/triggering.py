"""Helpers compartilhados para disparo automatico do Observer."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

OBSERVER_JOB_NAME = "workflow_observer_agent"
FALLBACK_FAILED_STATE = "UPSTREAM_FAILED"
ROOT_FAILURE_MARKERS = ("FAILED", "TIMEDOUT", "INTERNAL_ERROR", "CANCELED")


@dataclass(frozen=True)
class TriggerRuntimeContext:
    """Contexto minimo do job/task atual necessario para acionar o Observer."""

    parent_run_id: int
    job_id: int | None
    task_key: str | None


def _normalize_optional_int(value: Any) -> int | None:
    """Converte valores de tags/widgets em inteiro quando possivel."""
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    try:
        return int(text)
    except ValueError:
        return None


def normalize_task_state(value: Any) -> str:
    """Normaliza estados do Databricks para comparacao simples."""
    return str(value or "").strip().upper()


def is_root_failure_state(value: Any) -> bool:
    """Identifica falhas reais, ignorando apenas falhas em cascata."""
    state = normalize_task_state(value)
    if not state or state == FALLBACK_FAILED_STATE:
        return False
    return any(marker in state for marker in ROOT_FAILURE_MARKERS)


def extract_failed_task_keys(tasks: Sequence[Any] | None) -> list[str]:
    """Extrai task keys com falha real; se nao houver, faz fallback para upstream."""
    if not tasks:
        return []

    root_failed: list[str] = []
    fallback_failed: list[str] = []

    for task in tasks:
        task_key = getattr(task, "task_key", "") or ""
        state = normalize_task_state(getattr(getattr(task, "state", None), "result_state", None))
        if not task_key or not state:
            continue

        if is_root_failure_state(state):
            root_failed.append(task_key)
        elif state == FALLBACK_FAILED_STATE:
            fallback_failed.append(task_key)

    return root_failed or fallback_failed


def parse_failed_tasks_param(value: str) -> list[str]:
    """Aceita JSON ou lista separada por virgula vinda de widgets."""
    if not value:
        return []

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        parsed = [item.strip() for item in value.split(",")]

    if isinstance(parsed, str):
        parsed = [parsed]

    if not isinstance(parsed, list):
        return []

    cleaned = [str(item).strip() for item in parsed if str(item).strip()]
    # Preserva ordem e remove duplicados.
    return list(dict.fromkeys(cleaned))


def build_observer_notebook_params(
    *,
    catalog: str,
    scope: str,
    source_run_id: int,
    source_job_id: int | None,
    source_job_name: str,
    failed_tasks: Sequence[str] | None,
    llm_provider: str = "anthropic",
    git_provider: str = "github",
) -> dict[str, str]:
    """Monta notebook_params para o job do Observer."""
    return {
        "catalog": catalog,
        "scope": scope,
        "source_run_id": str(source_run_id),
        "source_job_id": str(source_job_id or ""),
        "source_job_name": source_job_name,
        "failed_tasks": json.dumps(list(dict.fromkeys(failed_tasks or []))),
        "llm_provider": llm_provider,
        "git_provider": git_provider,
    }


def resolve_runtime_context(
    tags: Mapping[str, str],
    *,
    current_run_id: Any = None,
) -> TriggerRuntimeContext:
    """Resolve o parent run do multitask job a partir das tags do notebook."""
    parent_run_id = (
        _normalize_optional_int(tags.get("multitaskParentRunId"))
        or _normalize_optional_int(tags.get("jobRunId"))
        or _normalize_optional_int(tags.get("runId"))
        or _normalize_optional_int(current_run_id)
    )
    if parent_run_id is None:
        raise ValueError("Nao foi possivel determinar o run_id do workflow atual")

    return TriggerRuntimeContext(
        parent_run_id=parent_run_id,
        job_id=_normalize_optional_int(tags.get("jobId")),
        task_key=tags.get("taskKey") or None,
    )
