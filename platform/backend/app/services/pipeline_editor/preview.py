"""Preview/export tenant-scoped para drafts do Pipeline Editor."""

from __future__ import annotations

import csv
import io
import uuid
from typing import TYPE_CHECKING, Literal

import structlog

from app.services.pipeline_editor.preview_sql import (
    PreviewSqlError,
    build_rows_after_sql,
    build_rows_before_sql,
    build_schema_delta,
    parse_query_result,
    preview_namespace,
)
from app.services.pipeline_editor.schemas import TransformDraft

if TYPE_CHECKING:
    from app.services.databricks_service import DatabricksService

logger = structlog.get_logger()

ExportFormat = Literal["csv", "parquet"]


class PreviewExportError(ValueError):
    """Erro de exportacao de preview (dados ausentes ou formato invalido)."""


def rows_to_csv_bytes(rows: list[dict]) -> bytes:
    """Serializa linhas de preview em CSV UTF-8."""
    buffer = io.StringIO()
    if not rows:
        buffer.write("")
        return buffer.getvalue().encode("utf-8")

    fieldnames = list(rows[0].keys())
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def rows_to_parquet_bytes(rows: list[dict]) -> bytes:
    """Serializa linhas de preview em Parquet via pyarrow (se disponivel)."""
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise PreviewExportError(
            "Exportacao Parquet indisponivel: instale pyarrow no backend."
        ) from exc

    if not rows:
        table = pa.table({})
    else:
        columns: dict[str, list] = {key: [] for key in rows[0]}
        for row in rows:
            for key in columns:
                columns[key].append(row.get(key))

        arrays = []
        names = []
        for name, values in columns.items():
            names.append(name)
            arrays.append(pa.array(values, type=pa.string()))
        table = pa.table(dict(zip(names, arrays, strict=False)))

    out = io.BytesIO()
    pq.write_table(table, out)
    return out.getvalue()


def export_preview_rows(rows: list[dict], export_format: ExportFormat) -> tuple[bytes, str]:
    """Retorna bytes do arquivo exportado e media type."""
    if export_format == "csv":
        return rows_to_csv_bytes(rows), "text/csv; charset=utf-8"
    if export_format == "parquet":
        return rows_to_parquet_bytes(rows), "application/vnd.apache.parquet"
    raise PreviewExportError(f"Formato de exportacao invalido: {export_format}")


def preview_rows_for_export(preview_result: dict | None) -> list[dict]:
    """Extrai linhas pos-transformacao do preview persistido."""
    if not preview_result:
        raise PreviewExportError("Preview ainda nao executado para esta versao.")
    if preview_result.get("status") != "ready":
        error = preview_result.get("error") or "Preview indisponivel para exportacao."
        raise PreviewExportError(str(error))
    rows = preview_result.get("rows_after") or []
    if not isinstance(rows, list):
        raise PreviewExportError("Preview sem linhas exportaveis.")
    return rows


def build_preview_result(
    *,
    company_id: uuid.UUID,
    pipeline_id: uuid.UUID,
    session_id: uuid.UUID,
    draft: TransformDraft,
    sample_rows: int,
    rows_before: list[dict] | None = None,
    rows_after: list[dict] | None = None,
    status: str = "ready",
    error: str | None = None,
    sql_warnings: list[str] | None = None,
) -> dict:
    """Monta payload de preview persistido na versao/artefato."""
    namespace = preview_namespace(
        company_id=str(company_id),
        pipeline_id=str(pipeline_id),
        session_id=str(session_id),
    )
    result = {
        "status": status,
        "company_id": str(company_id),
        "pipeline_id": str(pipeline_id),
        "session_id": str(session_id),
        "namespace": namespace,
        "sample_rows": sample_rows,
        "target_table": draft.target_table,
        "operations": [op.model_dump(exclude_none=True) for op in draft.operations],
        "schema_delta": build_schema_delta(draft.operations),
        "rows_before": rows_before or [],
        "rows_after": rows_after or [],
    }
    if error:
        result["error"] = error
    if sql_warnings:
        result["sql_warnings"] = sql_warnings
    return result


async def run_preview(
    databricks: DatabricksService,
    *,
    company_id: uuid.UUID,
    pipeline_id: uuid.UUID,
    session_id: uuid.UUID,
    draft: TransformDraft,
    sample_rows: int,
) -> dict:
    """Executa preview Silver via SQL Statement API (sem job Databricks)."""
    if draft.layer != "silver":
        return build_preview_result(
            company_id=company_id,
            pipeline_id=pipeline_id,
            session_id=session_id,
            draft=draft,
            sample_rows=sample_rows,
            status="failed",
            error="Pipeline Editor aceita apenas camada Silver.",
        )

    try:
        before_sql = build_rows_before_sql(draft.target_table, sample_rows)
        before_response = await databricks.query_table(before_sql, sample_rows)
        columns, rows_before = parse_query_result(before_response)

        after_sql, sql_warnings = build_rows_after_sql(
            draft.target_table,
            columns,
            draft.operations,
            sample_rows,
        )
        after_response = await databricks.query_table(after_sql, sample_rows)
        _, rows_after = parse_query_result(after_response)

        return build_preview_result(
            company_id=company_id,
            pipeline_id=pipeline_id,
            session_id=session_id,
            draft=draft,
            sample_rows=sample_rows,
            rows_before=rows_before,
            rows_after=rows_after,
            status="ready",
            sql_warnings=sql_warnings or None,
        )
    except PreviewSqlError as exc:
        logger.warning(
            "pipeline_editor_preview_sql_failed",
            table=draft.target_table,
            error=str(exc),
        )
        return build_preview_result(
            company_id=company_id,
            pipeline_id=pipeline_id,
            session_id=session_id,
            draft=draft,
            sample_rows=sample_rows,
            status="failed",
            error=str(exc),
        )
    except Exception as exc:
        logger.exception(
            "pipeline_editor_preview_failed",
            table=draft.target_table,
        )
        return build_preview_result(
            company_id=company_id,
            pipeline_id=pipeline_id,
            session_id=session_id,
            draft=draft,
            sample_rows=sample_rows,
            status="failed",
            error=str(exc),
        )


def build_export_result(
    *,
    company_id: uuid.UUID,
    pipeline_id: uuid.UUID,
    session_id: uuid.UUID,
    export_format: ExportFormat,
    preview_result: dict | None = None,
) -> dict:
    rows = preview_rows_for_export(preview_result)
    return {
        "status": "ready",
        "format": export_format,
        "company_id": str(company_id),
        "pipeline_id": str(pipeline_id),
        "session_id": str(session_id),
        "row_count": len(rows),
        "download_url": (
            f"/api/v1/pipelines/{pipeline_id}/edit-sessions/"
            f"{session_id}/exports/latest.{export_format}"
        ),
    }
