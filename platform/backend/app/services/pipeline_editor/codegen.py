"""Geração determinística de código PySpark a partir do DSL."""

from __future__ import annotations

from app.services.pipeline_editor.schemas import TransformDraft, TransformOperation


def _quote(value: str) -> str:
    return repr(value).replace("'", '"')


def _operation_to_pyspark(op: TransformOperation, dataframe: str) -> str:
    if op.op == "drop_column":
        return f"{dataframe} = {dataframe}.drop({_quote(op.column or '')})"
    if op.op == "rename_column":
        return (
            f"{dataframe} = {dataframe}.withColumnRenamed("
            f"{_quote(op.column or '')}, {_quote(op.new_name or '')})"
        )
    if op.op == "cast_column":
        return (
            f"{dataframe} = {dataframe}.withColumn("
            f"{_quote(op.column or '')}, "
            f"F.col({_quote(op.column or '')}).cast({_quote(op.data_type or '')}))"
        )
    if op.op == "trim":
        return (
            f"{dataframe} = {dataframe}.withColumn("
            f"{_quote(op.column or '')}, F.trim(F.col({_quote(op.column or '')})))"
        )
    if op.op == "regex_replace":
        return (
            f"{dataframe} = {dataframe}.withColumn("
            f"{_quote(op.column or '')}, "
            f"F.regexp_replace(F.col({_quote(op.column or '')}), "
            f"{_quote(op.pattern or '')}, {_quote(op.replacement or '')}))"
        )
    if op.op == "filter_rows":
        return f"{dataframe} = {dataframe}.filter({op.expression or 'F.lit(True)'})"
    if op.op == "derive_column":
        return (
            f"{dataframe} = {dataframe}.withColumn("
            f"{_quote(op.column or '')}, {op.expression or 'F.lit(None)'})"
        )
    if op.op == "date_format":
        return (
            f"{dataframe} = {dataframe}.withColumn("
            f"{_quote(op.column or '')}, "
            f"F.date_format(F.col({_quote(op.column or '')}), {_quote(op.format or '')}))"
        )
    if op.op == "json_extract":
        return (
            f"{dataframe} = {dataframe}.withColumn("
            f"{_quote(op.new_name or '')}, "
            f"F.get_json_object(F.col({_quote(op.column or '')}), {_quote(op.json_path or '')}))"
        )
    if op.op == "coalesce":
        cols = op.source_columns or ([op.column] if op.column else [])
        args = ", ".join(f"F.col({_quote(col)})" for col in cols)
        return (
            f"{dataframe} = {dataframe}.withColumn("
            f"{_quote(op.column or '')}, F.coalesce({args}))"
        )
    if op.op == "mask_pii":
        return (
            f"{dataframe} = {dataframe}.withColumn("
            f"{_quote(op.column or '')}, F.lit('[REDACTED]'))"
        )
    raise ValueError(f"Unsupported transform operation: {op.op}")


def generate_transform_block(draft: TransformDraft) -> str:
    """Gera célula Databricks com transformações do editor."""
    lines = [
        "# COMMAND ----------",
        "",
        "# DBTITLE 1,Transformacoes Low-Code do Pipeline Editor",
        "# Bloco gerado a partir de TransformDraft versionado na plataforma.",
        f"{draft.output_dataframe} = {draft.input_dataframe}",
    ]
    lines.extend(
        _operation_to_pyspark(operation, draft.output_dataframe)
        for operation in draft.operations
    )
    return "\n".join(lines) + "\n\n"


def generate_pyspark_patch(source: str, draft: TransformDraft) -> str:
    """Insere bloco gerado antes do primeiro write Delta e troca DF de saída."""
    marker = "# DBTITLE 1,Salvar como Delta Table e Upload para S3"
    if marker not in source:
        raise ValueError(f"Insertion marker not found: {marker}")

    block = generate_transform_block(draft)
    patched = source.replace(marker, f"{block}{marker}", 1)
    return patched.replace(
        f"{draft.input_dataframe}.write.format",
        f"{draft.output_dataframe}.write.format",
    )
