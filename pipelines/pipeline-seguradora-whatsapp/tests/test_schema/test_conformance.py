"""Testes de schema conformance (T6 Phase 1).

Usa `FakeDataFrame` que rastreia chamadas drop/withColumn/select em vez
de montar SparkSession. Validamos ordem + presença das chamadas; comportamento
real já é coberto por E2E no Databricks.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pipeline_lib.schema.conformance import conform_to_schema

# Factory fake pra evitar dep de pyspark nos testes locais
_NULL_FACTORY = lambda dtype: f"<NULL:{dtype}>"  # noqa: E731


@dataclass
class _FakeField:
    name: str
    dataType: str  # noqa: N815 — espelha pyspark StructField


@dataclass
class _FakeSchema:
    fields: list[_FakeField]


@dataclass
class _FakeDataFrame:
    columns: list[str]
    calls: list[tuple[str, tuple]] = field(default_factory=list)

    def drop(self, name: str) -> _FakeDataFrame:
        self.calls.append(("drop", (name,)))
        new_cols = [c for c in self.columns if c != name]
        return _FakeDataFrame(columns=new_cols, calls=self.calls)

    def withColumn(self, name: str, _lit_expr) -> _FakeDataFrame:  # noqa: N802
        self.calls.append(("withColumn", (name,)))
        return _FakeDataFrame(columns=[*self.columns, name], calls=self.calls)

    def select(self, *cols: str) -> _FakeDataFrame:
        self.calls.append(("select", tuple(cols)))
        return _FakeDataFrame(columns=list(cols), calls=self.calls)


SCHEMA = _FakeSchema(fields=[
    _FakeField("message_id", "string"),
    _FakeField("conversation_id", "string"),
    _FakeField("timestamp", "string"),
    _FakeField("direction", "string"),
])


class TestConformToSchema:
    def test_exact_match_just_reorders_and_selects(self):
        df = _FakeDataFrame(columns=["direction", "message_id", "conversation_id", "timestamp"])
        out = conform_to_schema(df, SCHEMA, null_value_factory=_NULL_FACTORY)
        # Nenhum drop, nenhum withColumn — só select na ordem do schema
        assert not any(c[0] == "drop" for c in df.calls)
        assert not any(c[0] == "withColumn" for c in df.calls)
        select_calls = [c for c in df.calls if c[0] == "select"]
        assert len(select_calls) == 1
        assert select_calls[0][1] == tuple(f.name for f in SCHEMA.fields)
        assert out.columns == ["message_id", "conversation_id", "timestamp", "direction"]

    def test_drops_extra_columns(self):
        df = _FakeDataFrame(columns=[
            "message_id",
            "conversation_id",
            "timestamp",
            "direction",
            "unexpected_column",
        ])
        conform_to_schema(df, SCHEMA, null_value_factory=_NULL_FACTORY)
        drops = [c[1][0] for c in df.calls if c[0] == "drop"]
        assert "unexpected_column" in drops

    def test_drops_chaos_column_with_error_log(self, caplog):
        df = _FakeDataFrame(columns=[
            "message_id",
            "conversation_id",
            "timestamp",
            "direction",
            "_chaos_invalid",
        ])
        conform_to_schema(df, SCHEMA, null_value_factory=_NULL_FACTORY)
        drops = [c[1][0] for c in df.calls if c[0] == "drop"]
        assert "_chaos_invalid" in drops
        # Log no nivel ERROR para chaos col
        assert any("CHAOS MODE" in r.message for r in caplog.records)

    def test_adds_missing_columns_as_null(self):
        df = _FakeDataFrame(columns=["message_id", "conversation_id"])
        conform_to_schema(df, SCHEMA, null_value_factory=_NULL_FACTORY)
        added = [c[1][0] for c in df.calls if c[0] == "withColumn"]
        assert set(added) == {"timestamp", "direction"}

    def test_final_select_in_schema_order(self):
        df = _FakeDataFrame(columns=["direction", "message_id", "extra"])
        conform_to_schema(df, SCHEMA, null_value_factory=_NULL_FACTORY)
        select_calls = [c for c in df.calls if c[0] == "select"]
        # Pelo menos 1 select no fim, em ordem do schema
        assert select_calls[-1][1] == (
            "message_id",
            "conversation_id",
            "timestamp",
            "direction",
        )

    def test_handles_combined_extra_and_missing(self):
        df = _FakeDataFrame(columns=["message_id", "_chaos_hack", "unknown"])
        conform_to_schema(df, SCHEMA, null_value_factory=_NULL_FACTORY)
        drops = [c[1][0] for c in df.calls if c[0] == "drop"]
        added = [c[1][0] for c in df.calls if c[0] == "withColumn"]
        assert {"_chaos_hack", "unknown"} <= set(drops)
        assert {"conversation_id", "timestamp", "direction"} <= set(added)
