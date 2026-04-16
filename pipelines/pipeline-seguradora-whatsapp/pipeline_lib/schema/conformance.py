"""Schema conformance para DataFrames Spark (T6 Phase 1).

Extraído de `notebooks/bronze/ingest.py` — era inline no notebook, sem
pytest. Agora lib pura com testes.

Regras:
- Colunas extras vão embora (com log warn para debug chaos).
- Colunas faltantes são adicionadas com NULL (schema evolution tolerado).
- Output = apenas colunas do schema esperado, na ordem dele.

Uso:
    from pipeline_lib.schema import conform_to_schema

    df_ok = conform_to_schema(df_raw, EXPECTED_SCHEMA)
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Protocol

logger = logging.getLogger(__name__)


class _SchemaField(Protocol):
    name: str
    dataType: object  # noqa: N815 — espelha pyspark.sql.types.StructField


class _SchemaLike(Protocol):
    """StructType com .fields (duck-typed para facilitar testes)."""

    fields: list[_SchemaField]


def _default_null_for(dtype):
    """Factory default: `lit(None).cast(dtype)` via pyspark (tardio)."""
    from pyspark.sql.functions import lit  # noqa: PLC0415

    return lit(None).cast(dtype)


def conform_to_schema(
    df,
    expected_schema: _SchemaLike,
    null_value_factory: Callable[[object], object] | None = None,
):
    """Conforma `df` ao `expected_schema`.

    - Remove colunas extras (logando o drop, com destaque pra `_chaos_*`).
    - Adiciona colunas faltantes como NULL do tipo declarado no schema.
    - Seleciona só as colunas esperadas, na ordem do schema.

    Args:
        df: Spark DataFrame de entrada.
        expected_schema: StructType descrevendo o contrato.
        null_value_factory: Callable que recebe um DataType e retorna a
            expressão "NULL tipado" a passar para `withColumn`. Default
            usa `F.lit(None).cast(dtype)`. Em testes, injete factory
            pura pra evitar dep de pyspark.

    Returns:
        Novo DataFrame Spark com o schema conformado.
    """
    null_factory = null_value_factory or _default_null_for

    expected_cols = [field.name for field in expected_schema.fields]
    expected_types = {field.name: field.dataType for field in expected_schema.fields}
    actual_cols = list(df.columns)

    # 1. Drop colunas extras
    extra_cols = set(actual_cols) - set(expected_cols)
    for col_name in extra_cols:
        if col_name.startswith("_chaos_"):
            logger.error("CHAOS MODE — coluna de teste detectada: %s", col_name)
        else:
            logger.warning("coluna extra removida: %s", col_name)
        df = df.drop(col_name)

    # 2. Adicionar colunas faltantes com NULL do tipo correto
    current_cols = set(df.columns)
    missing_cols = [c for c in expected_cols if c not in current_cols]
    for col_name in missing_cols:
        logger.warning("coluna faltante adicionada como NULL: %s", col_name)
        df = df.withColumn(col_name, null_factory(expected_types[col_name]))

    # 3. Reordenar + selecionar
    return df.select(*expected_cols)
