"""Testes unitarios para o modulo de persistencia do Observer."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from observer.persistence import (
    DiagnosticRecord,
    ObserverDiagnosticsStore,
    calculate_cost_usd,
    error_hash,
)

# ================================================================
# calculate_cost_usd
# ================================================================


class TestCalculateCostUsd:
    def test_anthropic_claude_opus_4(self):
        # 1000 in tokens * $15/M + 500 out * $75/M = $0.0525
        cost = calculate_cost_usd(
            "anthropic", "claude-opus-4-20250514", 1000, 500
        )
        assert cost == pytest.approx(0.0525, rel=1e-4)

    def test_anthropic_claude_sonnet(self):
        # 2000 in * $3/M + 1000 out * $15/M = $0.021
        cost = calculate_cost_usd(
            "anthropic", "claude-sonnet-3-5-20241022", 2000, 1000
        )
        assert cost == pytest.approx(0.021, rel=1e-4)

    def test_openai_gpt_4o(self):
        # 5000 in * $2.50/M + 2000 out * $10/M = $0.0325
        cost = calculate_cost_usd("openai", "gpt-4o", 5000, 2000)
        assert cost == pytest.approx(0.0325, rel=1e-4)

    def test_unknown_provider_returns_zero(self):
        cost = calculate_cost_usd("mistral", "mixtral-8x7b", 1000, 500)
        assert cost == 0.0

    def test_unknown_model_returns_zero(self):
        cost = calculate_cost_usd("anthropic", "claude-unknown-model", 1000, 500)
        assert cost == 0.0

    def test_zero_tokens(self):
        cost = calculate_cost_usd(
            "anthropic", "claude-opus-4-20250514", 0, 0
        )
        assert cost == 0.0

    def test_case_insensitive_provider(self):
        cost = calculate_cost_usd(
            "ANTHROPIC", "claude-opus-4-20250514", 1000, 500
        )
        assert cost == pytest.approx(0.0525, rel=1e-4)


# ================================================================
# error_hash
# ================================================================


class TestErrorHash:
    def test_deterministic(self):
        msg = "ValueError: CHAOS: Schema invalido"
        assert error_hash(msg) == error_hash(msg)

    def test_different_messages_produce_different_hashes(self):
        assert error_hash("erro A") != error_hash("erro B")

    def test_whitespace_normalized(self):
        # strip aplicado — espacos no inicio/fim nao afetam o hash
        assert error_hash("  erro  ") == error_hash("erro")

    def test_empty_message(self):
        # Vazio ainda gera um hash valido (do hash de string vazia)
        h = error_hash("")
        assert isinstance(h, str)
        assert len(h) == 64

    def test_returns_hex_string_64_chars(self):
        h = error_hash("qualquer erro")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


# ================================================================
# build_record
# ================================================================


@dataclass
class FakeDiagnosis:
    diagnosis: str = "erro de schema"
    root_cause: str = "coluna invalida injetada"
    fix_description: str = "remover coluna _chaos_invalid_col"
    fixed_code: str | None = "codigo corrigido"
    file_to_fix: str | None = "pipeline/notebooks/bronze/ingest.py"
    confidence: float = 0.85
    requires_human_review: bool = False
    provider: str = "anthropic"
    model: str = "claude-opus-4-20250514"
    input_tokens: int = 2377
    output_tokens: int = 628


@dataclass
class FakePR:
    pr_url: str = "https://github.com/owner/repo/pull/5"
    pr_number: int = 5
    branch_name: str = "fix/agent-auto-bronze-ingestion-20260410-000000"


class TestBuildRecord:
    def _store(self):
        return ObserverDiagnosticsStore(spark=None, catalog="medallion")

    def test_build_record_with_diagnosis_and_pr(self):
        store = self._store()
        record = store.build_record(
            job_id=777,
            job_name="medallion_pipeline_whatsapp",
            run_id=250661448283205,
            failed_task="bronze_ingestion",
            error_message="ValueError: CHAOS: Schema invalido",
            status="success",
            duration_seconds=12.345,
            diagnosis=FakeDiagnosis(),
            pr_result=FakePR(),
        )

        assert record.id
        assert record.job_id == 777
        assert record.job_name == "medallion_pipeline_whatsapp"
        assert record.run_id == 250661448283205
        assert record.failed_task == "bronze_ingestion"
        assert record.error_hash == error_hash("ValueError: CHAOS: Schema invalido")
        assert record.diagnosis == "erro de schema"
        assert record.confidence == 0.85
        assert record.provider == "anthropic"
        assert record.input_tokens == 2377
        assert record.output_tokens == 628
        # 2377 * 15/M + 628 * 75/M = 0.0353... + 0.0471 = 0.082755
        assert record.estimated_cost_usd == pytest.approx(0.082755, rel=1e-3)
        assert record.pr_url == "https://github.com/owner/repo/pull/5"
        assert record.pr_number == 5
        assert record.duration_seconds == 12.345
        assert record.status == "success"

    def test_build_record_without_pr(self):
        """Diagnostico completo mas sem PR (LLM respondeu mas nao gerou fix)."""
        store = self._store()
        diagnosis = FakeDiagnosis(fixed_code=None, file_to_fix=None)
        record = store.build_record(
            job_id=777,
            job_name="test",
            run_id=123,
            failed_task="x",
            error_message="erro",
            status="no_fix_proposed",
            duration_seconds=5.0,
            diagnosis=diagnosis,
            pr_result=None,
        )

        assert record.diagnosis == "erro de schema"
        assert record.pr_url == ""
        assert record.pr_number == 0
        assert record.status == "no_fix_proposed"

    def test_build_record_failure_without_diagnosis(self):
        """Falha total: LLM nao respondeu."""
        store = self._store()
        record = store.build_record(
            job_id=777,
            job_name="test",
            run_id=123,
            failed_task="x",
            error_message="erro",
            status="failed",
            duration_seconds=1.5,
            diagnosis=None,
            pr_result=None,
        )

        assert record.status == "failed"
        assert record.diagnosis == ""
        assert record.provider == ""
        assert record.estimated_cost_usd == 0.0


# ================================================================
# DiagnosticRecord
# ================================================================


class TestDiagnosticRecord:
    def test_to_row_dict_includes_all_fields(self):
        record = DiagnosticRecord(
            id="abc",
            job_id=123,
            failed_task="bronze_ingestion",
        )
        row = record.to_row_dict()
        assert row["id"] == "abc"
        assert row["job_id"] == 123
        assert row["failed_task"] == "bronze_ingestion"
        # Todos os 24 campos devem estar no dict
        expected_fields = {
            "id", "timestamp", "job_id", "job_name", "run_id", "failed_task",
            "error_message", "error_hash", "diagnosis", "root_cause",
            "fix_description", "file_to_fix", "confidence",
            "requires_human_review", "pr_url", "pr_number", "branch_name",
            "provider", "model", "input_tokens", "output_tokens",
            "estimated_cost_usd", "duration_seconds", "status",
        }
        assert set(row.keys()) == expected_fields


# ================================================================
# ObserverDiagnosticsStore (estrutura)
# ================================================================


class TestObserverDiagnosticsStoreStructure:
    def test_full_table_name_default_catalog(self):
        store = ObserverDiagnosticsStore(spark=None, catalog="medallion")
        assert store.full_table_name == "medallion.observer.diagnostics"

    def test_full_table_name_custom_catalog(self):
        store = ObserverDiagnosticsStore(spark=None, catalog="my_catalog")
        assert store.full_table_name == "my_catalog.observer.diagnostics"

    def test_schema_ddl_contains_all_columns(self):
        ddl = ObserverDiagnosticsStore.SCHEMA_DDL
        expected_columns = [
            "id", "timestamp", "job_id", "job_name", "run_id", "failed_task",
            "error_message", "error_hash", "diagnosis", "root_cause",
            "fix_description", "file_to_fix", "confidence",
            "requires_human_review", "pr_url", "pr_number", "branch_name",
            "provider", "model", "input_tokens", "output_tokens",
            "estimated_cost_usd", "duration_seconds", "status",
        ]
        for col in expected_columns:
            assert col in ddl
