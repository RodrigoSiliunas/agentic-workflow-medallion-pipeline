"""Testes do helper delta_row_count (T5 Phase 3/4)."""

from __future__ import annotations

from unittest.mock import MagicMock

from pipeline_lib.validation import delta_row_count


class _FakeRow(dict):
    def __getitem__(self, key):
        return super().__getitem__(key)


class _FakeSparkDescribeOK:
    def __init__(self, num_rows: int | None):
        self._num_rows = num_rows

    def sql(self, stmt: str):
        assert "DESCRIBE DETAIL" in stmt
        return self

    def collect(self):
        return [_FakeRow(numRows=self._num_rows)]


class _FakeSparkDescribeFails:
    def sql(self, _stmt: str):
        raise RuntimeError("no describe")

    def table(self, _name: str):
        df = MagicMock()
        df.count.return_value = 42
        return df


def test_returns_delta_num_rows_when_available():
    spark = _FakeSparkDescribeOK(num_rows=1234)
    assert delta_row_count(spark, "catalog.schema.table") == 1234


def test_falls_back_to_count_when_describe_fails():
    spark = _FakeSparkDescribeFails()
    assert delta_row_count(spark, "catalog.schema.table") == 42


def test_falls_back_when_num_rows_is_null():
    spark = _FakeSparkDescribeOK(num_rows=None)
    # precisa do fallback, que o FakeSparkDescribeOK não oferece — stub
    spark.table = MagicMock()
    spark.table.return_value.count.return_value = 7
    assert delta_row_count(spark, "catalog.schema.table") == 7


def test_returns_zero_when_everything_fails():
    spark = MagicMock()
    spark.sql.side_effect = RuntimeError("describe boom")
    spark.table.side_effect = RuntimeError("count boom")
    assert delta_row_count(spark, "catalog.schema.table") == 0
