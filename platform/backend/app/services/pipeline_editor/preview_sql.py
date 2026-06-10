"""Geração SQL para preview Silver via Databricks SQL Statement API."""

from __future__ import annotations

from app.services.pipeline_editor.codegen import cast_is_null_prone
from app.services.pipeline_editor.schemas import TransformOperation


class PreviewSqlError(ValueError):
    """Erro ao montar ou interpretar SQL de preview."""


def _normalize_table(table: str) -> str:
    """Normaliza identificador de tabela (sem crases, trim, case-insensitive)."""
    return ".".join(
        part.strip().replace("`", "").lower()
        for part in str(table).split(".")
        if part.strip()
    )


def validate_target_table(target_table: str, output_tables: list[str]) -> None:
    """Garante que o `target_table` do draft pertence aos `output_tables` do node.

    Sem esse cross-check contra o manifest, um tenant poderia apontar o draft
    para qualquer tabela do catalogo e fazer preview/export de dados arbitrarios.
    Levanta PreviewSqlError quando a tabela nao esta declarada no node.
    """
    target = _normalize_table(target_table)
    if not target:
        raise PreviewSqlError("Tabela alvo invalida para preview")

    allowed = {_normalize_table(table) for table in (output_tables or []) if table}
    if not allowed:
        raise PreviewSqlError(
            "No do manifest nao declara output_tables — preview/export bloqueado."
        )

    # Wildcard declarado (ex.: medallion.gold.*) cobre todo o schema do prefixo.
    for table in allowed:
        if table.endswith(".*"):
            prefix = table[:-1]  # mantem o ponto final do prefixo
            if target.startswith(prefix):
                return

    if target not in allowed:
        declared = ", ".join(sorted(allowed)) or "(nenhuma)"
        raise PreviewSqlError(
            f"Tabela alvo `{target_table}` nao pertence ao node "
            f"(output_tables declaradas: {declared})."
        )


def preview_namespace(
    *,
    company_id: str,
    pipeline_id: str,
    session_id: str,
) -> str:
    return (
        f"preview_{company_id[:8]}_{pipeline_id[:8]}_{session_id[:8]}"
    )


def quote_table(table: str) -> str:
    parts = [part.strip() for part in table.split(".") if part.strip()]
    if not parts:
        raise PreviewSqlError("Tabela alvo invalida para preview")
    return ".".join(f"`{part.replace('`', '')}`" for part in parts)


def quote_ident(name: str) -> str:
    return f"`{name.replace('`', '')}`"


def quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def build_rows_before_sql(table: str, limit: int) -> str:
    return f"SELECT * FROM {quote_table(table)} LIMIT {int(limit)}"


def build_rows_after_sql(
    table: str,
    columns: list[str],
    operations: list[TransformOperation],
    limit: int,
) -> tuple[str, list[str]]:
    """Monta SELECT transformado e retorna warnings de ops nao traduziveis."""
    warnings: list[str] = []
    col_state = {column: quote_ident(column) for column in columns}
    col_order = list(columns)
    dropped: set[str] = set()
    renames: dict[str, str] = {}
    derived: dict[str, str] = {}
    filters: list[str] = []

    for op in operations:
        if op.op == "drop_column" and op.column:
            dropped.add(op.column)
            col_state.pop(op.column, None)
            if op.column in col_order:
                col_order.remove(op.column)
        elif op.op == "rename_column" and op.column and op.new_name:
            renames[op.column] = op.new_name
        elif op.op == "trim" and op.column:
            ref = col_state.get(op.column, quote_ident(op.column))
            col_state[op.column] = f"TRIM({ref})"
        elif op.op == "cast_column" and op.column and op.data_type:
            ref = col_state.get(op.column, quote_ident(op.column))
            # Guardrail: cast null-prone usa try_cast (NULL explicito, sem erro)
            # e sinaliza risco de NULL no preview via warning.
            if cast_is_null_prone(op.data_type):
                col_state[op.column] = f"try_cast({ref} AS {op.data_type})"
                warnings.append(
                    f"cast_column `{op.column}` para `{op.data_type}` pode gerar NULL "
                    "em valores incompativeis (try_cast retorna NULL sem erro)."
                )
            else:
                col_state[op.column] = f"CAST({ref} AS {op.data_type})"
        elif op.op == "regex_replace" and op.column:
            ref = col_state.get(op.column, quote_ident(op.column))
            col_state[op.column] = (
                f"regexp_replace({ref}, {quote_literal(op.pattern or '')}, "
                f"{quote_literal(op.replacement or '')})"
            )
        elif op.op == "date_format" and op.column and op.format:
            ref = col_state.get(op.column, quote_ident(op.column))
            col_state[op.column] = f"date_format({ref}, {quote_literal(op.format)})"
        elif op.op == "coalesce" and op.column:
            cols = op.source_columns or ([op.column] if op.column else [])
            args = ", ".join(
                col_state.get(name, quote_ident(name)) for name in cols if name
            )
            col_state[op.column] = f"COALESCE({args})"
        elif op.op == "mask_pii" and op.column:
            col_state[op.column] = quote_literal("[REDACTED]")
        elif op.op == "derive_column" and op.column and op.expression:
            if "F." in op.expression:
                warnings.append(
                    f"derive_column `{op.column}` usa PySpark; preview SQL ignora expressao."
                )
            else:
                derived[op.column] = op.expression
        elif op.op == "json_extract" and op.column and op.new_name and op.json_path:
            ref = col_state.get(op.column, quote_ident(op.column))
            derived[op.new_name] = (
                f"get_json_object({ref}, {quote_literal(op.json_path)})"
            )
        elif op.op == "filter_rows" and op.expression:
            if "F." in op.expression:
                warnings.append("filter_rows usa PySpark; preview SQL ignora filtro.")
            else:
                filters.append(op.expression)

    select_parts: list[str] = []
    for column in col_order:
        if column in dropped:
            continue
        expr = col_state.get(column, quote_ident(column))
        out_name = renames.get(column, column)
        if out_name != column or expr != quote_ident(column):
            select_parts.append(f"{expr} AS {quote_ident(out_name)}")
        else:
            select_parts.append(expr)

    for name, expr in derived.items():
        select_parts.append(f"({expr}) AS {quote_ident(name)}")

    if not select_parts:
        select_parts.append("*")

    sql = f"SELECT {', '.join(select_parts)} FROM {quote_table(table)}"
    if filters:
        sql += f" WHERE {' AND '.join(f'({item})' for item in filters)}"
    sql += f" LIMIT {int(limit)}"
    return sql, warnings


def parse_query_result(response: dict) -> tuple[list[str], list[dict]]:
    """Converte resposta da SQL Statement API em colunas + linhas dict."""
    state = str((response.get("status") or {}).get("state", "")).upper()
    if state and state not in {"SUCCEEDED", "PENDING", "RUNNING"}:
        error = (response.get("status") or {}).get("error") or {}
        message = error.get("message") or f"Query SQL falhou com estado {state}"
        raise PreviewSqlError(message)

    columns = [
        str(col.get("name"))
        for col in (response.get("manifest") or {}).get("schema", {}).get("columns", [])
        if col.get("name")
    ]
    data_array = (response.get("result") or {}).get("data_array") or []
    rows: list[dict] = []
    for raw_row in data_array:
        if not isinstance(raw_row, list):
            continue
        row = dict(zip(columns, raw_row, strict=False)) if columns else {}
        rows.append(row)
    return columns, rows


def build_schema_delta(operations: list[TransformOperation]) -> dict:
    return {
        "dropped": [op.column for op in operations if op.op == "drop_column" and op.column],
        "renamed": [
            {"from": op.column, "to": op.new_name}
            for op in operations
            if op.op == "rename_column" and op.column and op.new_name
        ],
        "derived": [
            op.column
            for op in operations
            if op.op in {"derive_column", "json_extract"}
            and (op.column or op.new_name)
        ],
    }
