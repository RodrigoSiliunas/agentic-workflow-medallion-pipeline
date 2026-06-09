"""Geração determinística de código PySpark a partir do DSL."""

from __future__ import annotations

from app.services.pipeline_editor.manifest import PipelineManifestNode
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


def generate_transform_block(write_df: str, operations: list[TransformOperation]) -> str:
    """Gera célula Databricks com transformações do editor.

    Muta `write_df` in-place — sem introduzir df_editor/df_parsed mágicos.
    O `.write` existente no notebook continua consumindo o mesmo nome de DF.
    """
    lines = [
        "# COMMAND ----------",
        "",
        "# DBTITLE 1,Transformacoes Low-Code do Pipeline Editor",
        "# Bloco gerado a partir de TransformDraft versionado na plataforma.",
    ]
    lines.extend(_operation_to_pyspark(op, write_df) for op in operations)
    return "\n".join(lines) + "\n\n"


def generate_pyspark_patch(
    source: str,
    draft: TransformDraft,
    *,
    node: PipelineManifestNode,
) -> str:
    """Insere bloco gerado antes do marker de write Delta.

    Usa `node.write_dataframe` como DF alvo — o mesmo DF que o notebook já
    escreve via `.write.format("delta")`. Sem troca de string frágil.
    """
    if not node.write_dataframe:
        raise ValueError(
            f"Node `{node.id}` nao declara write_dataframe — "
            "adicione o campo no manifest."
        )
    marker = node.insertion_marker
    if marker not in source:
        raise ValueError(f"Insertion marker not found: {marker}")

    block = generate_transform_block(node.write_dataframe, draft.operations)
    return source.replace(marker, f"{block}{marker}", 1)
