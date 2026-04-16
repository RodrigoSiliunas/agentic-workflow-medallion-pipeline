"""Métricas O(1) lidas do transaction log Delta (T5 PERF-09, PERF-17).

`DESCRIBE DETAIL` retorna num_rows direto do metadata — sem scan de
dados. Para tabelas não-Delta ou colunas num_rows nulas, cai em
`count()` como fallback.

Uso:
    from pipeline_lib.validation import delta_row_count

    rows = delta_row_count(spark, "medallion.bronze.conversations")
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def delta_row_count(spark, full_table_name: str) -> int:
    """Retorna numRows da tabela via DESCRIBE DETAIL ou fallback count().

    Args:
        spark: SparkSession.
        full_table_name: Nome totalmente qualificado (catalog.schema.table).

    Returns:
        int: contagem de linhas. Fallback 0 se até count() falhar.
    """
    try:
        detail = spark.sql(f"DESCRIBE DETAIL {full_table_name}").collect()[0]
        num_rows = detail["numRows"]
        if num_rows is not None:
            return int(num_rows)
    except Exception as exc:  # noqa: BLE001
        logger.debug(
            "DESCRIBE DETAIL falhou para %s: %s — usando fallback count()",
            full_table_name,
            exc,
        )

    # Fallback — tabela não-Delta, stats ausentes ou permissão
    try:
        return spark.table(full_table_name).count()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "count() fallback falhou para %s: %s",
            full_table_name,
            exc,
        )
        return 0
