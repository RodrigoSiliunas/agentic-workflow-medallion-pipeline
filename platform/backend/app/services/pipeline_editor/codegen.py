"""Geração determinística de código PySpark a partir do DSL."""

from __future__ import annotations

import re

from app.services.pipeline_editor.manifest import PipelineManifestNode
from app.services.pipeline_editor.schemas import TransformDraft, TransformOperation

# Casts cujo overflow/parse incompativel produz NULL silencioso no Spark.
# Para esses, o codegen usa F.try_cast (mesmo NULL, mas explicito) + aviso.
_NULL_PRONE_CAST_TARGETS = {
    "int",
    "integer",
    "bigint",
    "long",
    "smallint",
    "short",
    "tinyint",
    "byte",
    "double",
    "float",
    "decimal",
    "date",
    "timestamp",
    "boolean",
}

# Ops que alteram o schema (somem/renomeiam colunas). Exigem overwriteSchema
# no write Delta para nao deixar a coluna antiga como ghost null na tabela.
_SCHEMA_CHANGING_OPS = {"drop_column", "rename_column"}


def _quote(value: str) -> str:
    return repr(value).replace("'", '"')


def _normalize_cast_type(data_type: str) -> str:
    """Extrai o tipo base de um data_type (ex.: `decimal(10,2)` -> `decimal`)."""
    return re.split(r"[(\s]", data_type.strip().lower(), maxsplit=1)[0]


def cast_is_null_prone(data_type: str | None) -> bool:
    """True se o cast pode gerar NULL silencioso em valores incompativeis."""
    if not data_type:
        return False
    return _normalize_cast_type(data_type) in _NULL_PRONE_CAST_TARGETS


def _operation_to_pyspark(op: TransformOperation, dataframe: str) -> str:
    if op.op == "drop_column":
        return f"{dataframe} = {dataframe}.drop({_quote(op.column or '')})"
    if op.op == "rename_column":
        # IDEMPOTENTE: re-execucoes (e blocos empilhados de edits anteriores)
        # podem encontrar a coluna ja renomeada OU o destino ja existente
        # (ex.: ghost de mergeSchema) — rename incondicional explode com
        # COLUMN_ALREADY_EXISTS (achado no E2E real, run 1019391853336863).
        src = _quote(op.column or "")
        dst = _quote(op.new_name or "")
        return (
            f"if {src} in {dataframe}.columns and {dst} not in {dataframe}.columns:\n"
            f"    {dataframe} = {dataframe}.withColumnRenamed({src}, {dst})"
        )
    if op.op == "cast_column":
        # Guardrail: cast incompativel vira NULL silencioso. Usa F.try_cast
        # (NULL explicito, sem exception) + aviso inline para casts null-prone.
        column = _quote(op.column or "")
        data_type = _quote(op.data_type or "")
        if cast_is_null_prone(op.data_type):
            return (
                f"# AVISO: cast de {op.column!r} para {op.data_type!r} pode gerar NULL "
                "em valores incompativeis (try_cast nao lanca erro, retorna NULL).\n"
                f"{dataframe} = {dataframe}.withColumn("
                f"{column}, F.try_cast(F.col({column}), {data_type}))"
            )
        return (
            f"{dataframe} = {dataframe}.withColumn("
            f"{column}, F.col({column}).cast({data_type}))"
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


def _has_schema_changing_op(operations: list[TransformOperation]) -> bool:
    """True se alguma op renomeia/dropa coluna (precisa overwriteSchema)."""
    return any(op.op in _SCHEMA_CHANGING_OPS for op in operations)


def enforce_overwrite_schema(source: str, write_dataframe: str) -> str:
    """Forca overwriteSchema=true no write Delta do DF alvo (anti-ghost).

    Com `mergeSchema=true` + `mode("overwrite")`, colunas removidas/renomeadas
    persistem na tabela Delta como ghost null. `overwriteSchema=true` substitui
    o schema inteiro, dropando de fato a coluna antiga.

    Faz duas coisas, escopadas ao bloco de write de `write_dataframe`:
    1. Troca `.option("mergeSchema", ...)` por `.option("overwriteSchema", "true")`.
    2. Se nao houver opcao de schema, injeta `.option("overwriteSchema", "true")`.
    """
    # Localiza o bloco do write: de `{df}.write` ate o `.saveAsTable(...)`.
    write_pattern = re.compile(
        rf"({re.escape(write_dataframe)}\.write\b.*?\.saveAsTable\([^)]*\))",
        re.DOTALL,
    )

    def _patch_write_block(match: re.Match[str]) -> str:
        block = match.group(1)
        # 1. Substitui mergeSchema (qualquer valor) por overwriteSchema=true.
        if re.search(r"\.option\(\s*[\"']mergeSchema[\"']", block):
            return re.sub(
                r"\.option\(\s*[\"']mergeSchema[\"']\s*,\s*[\"'][^\"']*[\"']\s*\)",
                '.option("overwriteSchema", "true")',
                block,
                count=1,
            )
        # 2. Ja usa overwriteSchema — nada a fazer.
        if re.search(r"\.option\(\s*[\"']overwriteSchema[\"']", block):
            return block
        # 3. Sem opcao de schema — injeta overwriteSchema apos `.mode(...)`,
        #    ou antes do `.saveAsTable(...)` como fallback.
        mode_match = re.search(r"(\.mode\([^)]*\))", block)
        injection = '.option("overwriteSchema", "true")'
        if mode_match:
            insert_at = mode_match.end()
            return block[:insert_at] + injection + block[insert_at:]
        return re.sub(
            r"(\.saveAsTable\()",
            injection + r"\1",
            block,
            count=1,
        )

    return write_pattern.sub(_patch_write_block, source, count=1)


def generate_pyspark_patch(
    source: str,
    draft: TransformDraft,
    *,
    node: PipelineManifestNode,
) -> str:
    """Insere bloco gerado antes do marker de write Delta.

    Usa `node.write_dataframe` como DF alvo — o mesmo DF que o notebook já
    escreve via `.write.format("delta")`. Sem troca de string frágil.

    Quando o draft renomeia/dropa coluna, forca `overwriteSchema=true` no write
    Delta para que a coluna antiga seja REMOVIDA da tabela (sem ghost null).
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
    patched = source.replace(marker, f"{block}{marker}", 1)

    if _has_schema_changing_op(draft.operations):
        patched = enforce_overwrite_schema(patched, node.write_dataframe)

    return patched
