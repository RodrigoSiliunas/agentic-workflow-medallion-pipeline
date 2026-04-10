"""Testes unitarios para a logica de deduplicacao do Observer."""

from __future__ import annotations

from typing import Any

from observer.dedup import (
    DuplicateCheckResult,
    check_duplicate,
)
from observer.persistence import error_hash

# ================================================================
# Fakes para isolar store e git_provider
# ================================================================


class FakeStore:
    """Store falso que retorna uma lista fixa para find_recent_successful."""

    def __init__(self, existing: list[dict] | None = None, should_raise: bool = False):
        self.existing = existing or []
        self.should_raise = should_raise
        self.calls: list[tuple[str, int]] = []

    def find_recent_successful(
        self, error_hash_value: str, window_hours: int = 24
    ) -> list[dict]:
        if self.should_raise:
            raise RuntimeError("spark.sql failed")
        self.calls.append((error_hash_value, window_hours))
        return list(self.existing)


class FakeGitProvider:
    """Git provider falso com status configuravel por pr_number."""

    def __init__(self, statuses: dict[int, str] | None = None, raise_on: int | None = None):
        self.statuses = statuses or {}
        self.raise_on = raise_on
        self.calls: list[int] = []

    def get_pr_status(self, pr_number: int) -> str:
        self.calls.append(pr_number)
        if self.raise_on == pr_number:
            raise RuntimeError("github api down")
        return self.statuses.get(pr_number, "unknown")


def _make_record(pr_number: int = 5, pr_url: str = "https://github.com/o/r/pull/5") -> dict:
    return {
        "id": "abc-123",
        "timestamp": "2026-04-10T03:00:00",
        "job_id": 777,
        "job_name": "medallion_pipeline_whatsapp",
        "run_id": 42,
        "failed_task": "bronze_ingestion",
        "error_hash": error_hash("erro X"),
        "pr_url": pr_url,
        "pr_number": pr_number,
        "branch_name": "fix/agent-auto-bronze-ingestion-20260410",
        "confidence": 0.85,
        "status": "success",
    }


# ================================================================
# Cenarios sem diagnostico anterior (cache miss)
# ================================================================


class TestCacheMiss:
    def test_no_previous_returns_not_duplicate(self):
        store = FakeStore(existing=[])
        result = check_duplicate(store, "erro X")

        assert result.is_duplicate is False
        assert result.reason == "no_previous_success"
        assert result.existing_record is None

    def test_no_previous_hashes_the_error(self):
        store = FakeStore(existing=[])
        check_duplicate(store, "erro X", window_hours=48)

        assert store.calls == [(error_hash("erro X"), 48)]

    def test_store_query_failure_allows_diagnosis(self):
        store = FakeStore(should_raise=True)
        result = check_duplicate(store, "erro X")

        assert result.is_duplicate is False
        assert result.reason == "dedup_query_failed"


# ================================================================
# Cenarios com diagnostico anterior mas sem git provider
# ================================================================


class TestWithoutGitProvider:
    def test_previous_success_without_git_provider_is_duplicate(self):
        store = FakeStore(existing=[_make_record()])
        result = check_duplicate(store, "erro X", git_provider=None)

        assert result.is_duplicate is True
        assert result.reason == "previous_success_no_git_check"
        assert result.existing_record is not None
        assert result.existing_record["pr_number"] == 5


# ================================================================
# Cenarios com git provider — PR existente
# ================================================================


class TestWithGitProvider:
    def test_previous_pr_open_is_duplicate(self):
        store = FakeStore(existing=[_make_record(pr_number=5)])
        git = FakeGitProvider(statuses={5: "open"})

        result = check_duplicate(store, "erro X", git_provider=git)

        assert result.is_duplicate is True
        assert result.reason == "previous_pr_open"
        assert git.calls == [5]

    def test_previous_pr_merged_is_duplicate(self):
        store = FakeStore(existing=[_make_record(pr_number=5)])
        git = FakeGitProvider(statuses={5: "merged"})

        result = check_duplicate(store, "erro X", git_provider=git)

        assert result.is_duplicate is True
        assert result.reason == "previous_pr_merged"

    def test_previous_pr_closed_allows_rediagnosis(self):
        store = FakeStore(existing=[_make_record(pr_number=5)])
        git = FakeGitProvider(statuses={5: "closed"})

        result = check_duplicate(store, "erro X", git_provider=git)

        assert result.is_duplicate is False
        assert result.reason == "previous_pr_closed_without_merge"

    def test_previous_pr_status_unknown_is_duplicate_safe_default(self):
        store = FakeStore(existing=[_make_record(pr_number=5)])
        git = FakeGitProvider(statuses={})  # get_pr_status retorna 'unknown'

        result = check_duplicate(store, "erro X", git_provider=git)

        assert result.is_duplicate is True
        assert result.reason == "previous_pr_status_unknown"

    def test_git_provider_exception_is_duplicate_safe_default(self):
        store = FakeStore(existing=[_make_record(pr_number=5)])
        git = FakeGitProvider(raise_on=5)

        result = check_duplicate(store, "erro X", git_provider=git)

        assert result.is_duplicate is True
        assert result.reason == "pr_status_check_failed"

    def test_existing_record_without_pr_number_is_duplicate(self):
        store = FakeStore(existing=[_make_record(pr_number=0)])
        git = FakeGitProvider()

        result = check_duplicate(store, "erro X", git_provider=git)

        assert result.is_duplicate is True
        assert result.reason == "previous_success_without_pr_number"
        # Nao deve chamar git — nao ha PR para consultar
        assert git.calls == []


# ================================================================
# Configuracao da janela
# ================================================================


class TestWindow:
    def test_default_window_is_24h(self):
        store = FakeStore(existing=[])
        check_duplicate(store, "erro X")

        assert store.calls[0][1] == 24

    def test_custom_window(self):
        store = FakeStore(existing=[])
        check_duplicate(store, "erro X", window_hours=72)

        assert store.calls[0][1] == 72


# ================================================================
# DuplicateCheckResult
# ================================================================


class TestDuplicateCheckResult:
    def test_default_existing_record_is_none(self):
        result = DuplicateCheckResult(is_duplicate=False, reason="ok")
        assert result.existing_record is None

    def test_stores_existing_record(self):
        rec: dict[str, Any] = {"id": "x", "pr_number": 9}
        result = DuplicateCheckResult(
            is_duplicate=True, reason="hit", existing_record=rec
        )
        assert result.existing_record == rec
