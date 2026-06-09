"""Analisador de impacto downstream para operações no Pipeline Editor.

Detecta referências a colunas Silver em notebooks Gold e Validation,
bloqueando approve quando drop_column/rename_column afetariam código downstream.
"""

from __future__ import annotations

import re
from typing import NamedTuple

from app.services.pipeline_editor.schemas import TransformDraft

# Operações que quebram código downstream ao alterar o nome da coluna
BLOCKING_OPS = frozenset({"drop_column", "rename_column"})


class DownstreamRef(NamedTuple):
    file: str
    line: int
    snippet: str


def find_column_references(column: str, source: str, path: str) -> list[DownstreamRef]:
    """Varre source linha a linha e retorna cada linha que referencia column pelo nome.

    Usa word-boundary para evitar falsos positivos em nomes similares.
    """
    pattern = re.compile(r"\b" + re.escape(column) + r"\b")
    refs: list[DownstreamRef] = []
    for lineno, raw_line in enumerate(source.splitlines(), start=1):
        if pattern.search(raw_line):
            refs.append(DownstreamRef(file=path, line=lineno, snippet=raw_line.strip()))
    return refs


def check_downstream_impact(
    draft: TransformDraft,
    notebook_sources: dict[str, str],
) -> dict:
    """Analisa se as operações do draft afetam notebooks downstream.

    Args:
        draft: Draft com as operações de transformação.
        notebook_sources: Mapa de {caminho_relativo: conteúdo} dos notebooks a escanear.

    Returns:
        {
            "blocked": bool,
            "affected": [
                {
                    "column": str,
                    "op": str,
                    "references": [{"file": str, "line": int, "snippet": str}]
                }
            ]
        }
    """
    affected: list[dict] = []

    for op in draft.operations:
        if op.op not in BLOCKING_OPS or not op.column:
            continue

        all_refs: list[DownstreamRef] = []
        for path, source in notebook_sources.items():
            all_refs.extend(find_column_references(op.column, source, path))

        if all_refs:
            affected.append(
                {
                    "column": op.column,
                    "op": op.op,
                    "references": [
                        {"file": ref.file, "line": ref.line, "snippet": ref.snippet}
                        for ref in all_refs
                    ],
                }
            )

    return {"blocked": bool(affected), "affected": affected}
