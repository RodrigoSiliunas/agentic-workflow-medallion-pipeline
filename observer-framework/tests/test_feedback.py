"""Testes unitarios para o feedback loop do Observer."""

from __future__ import annotations

import pytest

from observer.persistence import ObserverDiagnosticsStore


class FakeSparkSession:
    """Spark fake que captura SQL executado e retorna dados controlados."""

    def __init__(self, describe_rows: list[dict] | None = None):
        self.queries: list[str] = []
        self.describe_rows = describe_rows or []

    def sql(self, statement: str):
        self.queries.append(statement.strip())
        return FakeDataFrame(self.describe_rows, statement)


class FakeRow:
    def __init__(self, data: dict):
        self._data = data

    def __getitem__(self, key):
        return self._data.get(key, "")


class FakeDataFrame:
    def __init__(self, rows: list[dict], statement: str):
        self._rows = rows
        self._statement = statement

    def collect(self):
        if "DESCRIBE TABLE" in self._statement.upper():
            return [FakeRow(r) for r in self._rows]
        return []


# ================================================================
# update_pr_feedback
# ================================================================


class TestUpdatePrFeedback:
    def test_merged_status(self):
        spark = FakeSparkSession()
        store = ObserverDiagnosticsStore(spark, catalog="medallion")

        store.update_pr_feedback(pr_number=5, pr_status="merged")

        assert len(spark.queries) == 1
        sql = spark.queries[0]
        assert "UPDATE medallion.observer.diagnostics" in sql
        assert "pr_status = 'merged'" in sql
        assert "feedback = 'fix_accepted'" in sql
        assert "WHERE pr_number = 5" in sql
        assert "resolution_time_hours" in sql

    def test_closed_status(self):
        spark = FakeSparkSession()
        store = ObserverDiagnosticsStore(spark, catalog="medallion")

        store.update_pr_feedback(pr_number=9, pr_status="closed")

        sql = spark.queries[0]
        assert "pr_status = 'closed'" in sql
        assert "feedback = 'fix_rejected'" in sql
        assert "WHERE pr_number = 9" in sql

    def test_invalid_status_raises(self):
        spark = FakeSparkSession()
        store = ObserverDiagnosticsStore(spark, catalog="medallion")

        with pytest.raises(ValueError, match="pr_status invalido"):
            store.update_pr_feedback(pr_number=5, pr_status="open")

    def test_zero_pr_number_raises(self):
        spark = FakeSparkSession()
        store = ObserverDiagnosticsStore(spark, catalog="medallion")

        with pytest.raises(ValueError, match="pr_number invalido"):
            store.update_pr_feedback(pr_number=0, pr_status="merged")

    def test_negative_pr_number_raises(self):
        spark = FakeSparkSession()
        store = ObserverDiagnosticsStore(spark, catalog="medallion")

        with pytest.raises(ValueError, match="pr_number invalido"):
            store.update_pr_feedback(pr_number=-1, pr_status="merged")

    def test_uses_custom_catalog(self):
        spark = FakeSparkSession()
        store = ObserverDiagnosticsStore(spark, catalog="my_catalog")

        store.update_pr_feedback(pr_number=5, pr_status="merged")

        assert "UPDATE my_catalog.observer.diagnostics" in spark.queries[0]


# ================================================================
# SCHEMA_DDL e MIGRATED_COLUMNS incluem campos de feedback
# ================================================================


class TestSchemaIncludesFeedbackColumns:
    def test_ddl_has_feedback_columns(self):
        ddl = ObserverDiagnosticsStore.SCHEMA_DDL
        for col in ("pr_status", "pr_resolved_at", "resolution_time_hours", "feedback"):
            assert col in ddl, f"coluna {col} ausente no SCHEMA_DDL"

    def test_migrated_columns_cover_all_feedback_fields(self):
        cols = {name for name, _type in ObserverDiagnosticsStore.MIGRATED_COLUMNS}
        expected = {"pr_status", "pr_resolved_at", "resolution_time_hours", "feedback"}
        assert expected.issubset(cols)

    def test_migrated_columns_types(self):
        by_name = dict(ObserverDiagnosticsStore.MIGRATED_COLUMNS)
        assert by_name["pr_status"] == "STRING"
        assert by_name["pr_resolved_at"] == "TIMESTAMP"
        assert by_name["resolution_time_hours"] == "DOUBLE"
        assert by_name["feedback"] == "STRING"


# ================================================================
# _migrate_columns (idempotencia)
# ================================================================


class TestMigrateColumns:
    def test_skips_columns_that_already_exist(self):
        # DESCRIBE retorna todas as colunas ja — nao deve rodar ALTER TABLE
        existing_cols = [
            {"col_name": "id"},
            {"col_name": "timestamp"},
            {"col_name": "pr_status"},
            {"col_name": "pr_resolved_at"},
            {"col_name": "resolution_time_hours"},
            {"col_name": "feedback"},
        ]
        spark = FakeSparkSession(describe_rows=existing_cols)
        store = ObserverDiagnosticsStore(spark, catalog="medallion")

        store._migrate_columns()

        alters = [q for q in spark.queries if q.startswith("ALTER TABLE")]
        assert alters == []  # nada a adicionar

    def test_adds_missing_columns(self):
        # DESCRIBE retorna tabela "antiga" sem os campos de feedback
        existing_cols = [
            {"col_name": "id"},
            {"col_name": "timestamp"},
            {"col_name": "status"},
        ]
        spark = FakeSparkSession(describe_rows=existing_cols)
        store = ObserverDiagnosticsStore(spark, catalog="medallion")

        store._migrate_columns()

        alters = [q for q in spark.queries if q.startswith("ALTER TABLE")]
        assert len(alters) == 4  # 4 colunas de feedback
        joined = " ".join(alters)
        assert "pr_status" in joined
        assert "pr_resolved_at" in joined
        assert "resolution_time_hours" in joined
        assert "feedback" in joined

    def test_ignores_header_rows(self):
        # DESCRIBE TABLE inclui linhas como "# Partitioning" que devem ser ignoradas
        existing_cols = [
            {"col_name": "id"},
            {"col_name": "# Detailed Table Information"},
            {"col_name": "pr_status"},
        ]
        spark = FakeSparkSession(describe_rows=existing_cols)
        store = ObserverDiagnosticsStore(spark, catalog="medallion")

        store._migrate_columns()

        alters = [q for q in spark.queries if q.startswith("ALTER TABLE")]
        # pr_status existe, faltam 3
        assert len(alters) == 3
