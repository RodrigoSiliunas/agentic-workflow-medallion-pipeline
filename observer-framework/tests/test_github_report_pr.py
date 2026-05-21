"""Testes unitarios para GitHubProvider.create_report_pr.

Cobre o caminho de PR de relatorio (sem code change aplicavel) usado quando
o LLM propoe conteudo identico a base (ZeroDiff) ou outros casos onde o
diagnostico precisa ser surfaceado em PR mesmo sem diff a aplicar.
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import pytest

from observer.providers.base import DiagnosisResult, GitProvider, PRResult


def _make_provider_and_mocks(monkeypatch, base_branch: str = "dev"):
    """Mocka o modulo `github` e retorna (provider, fake_repo, fake_pr)."""
    from observer.providers.github_provider import GitHubProvider

    fake_pygithub = MagicMock()
    fake_repo = MagicMock()

    # get_git_ref devolve ref com sha — usado pra criar branch nova.
    fake_ref = MagicMock()
    fake_ref.object.sha = "deadbeefcafe"
    fake_repo.get_git_ref.return_value = fake_ref

    # create_pull devolve objeto PR com html_url + number.
    fake_pr = MagicMock()
    fake_pr.html_url = "https://github.com/owner/repo/pull/42"
    fake_pr.number = 42
    fake_repo.create_pull.return_value = fake_pr

    # get_issue(pr_number).set_labels(...) — usado pra labels.
    fake_issue = MagicMock()
    fake_repo.get_issue.return_value = fake_issue

    fake_pygithub.return_value.get_repo.return_value = fake_repo

    fake_module = types.ModuleType("github")
    fake_module.Github = fake_pygithub
    fake_module.Auth = MagicMock()
    monkeypatch.setitem(sys.modules, "github", fake_module)

    provider = GitHubProvider(
        token="fake", repo="owner/repo", base_branch=base_branch
    )
    return provider, fake_repo, fake_pr


def _make_diagnosis(**overrides) -> DiagnosisResult:
    """DiagnosisResult com defaults razoaveis pros testes."""
    base = {
        "diagnosis": "SyntaxError na linha 12",
        "root_cause": "indentacao quebrada apos try sem except",
        "fix_description": "adicionar bloco except ou corrigir indent",
        "fixed_code": "print('ok')\n",
        "file_to_fix": "pipelines/whatsapp/notebooks/bronze/ingest.py",
        "confidence": 0.98,
        "requires_human_review": False,
        "provider": "anthropic",
        "model": "claude-opus-4-7",
        "input_tokens": 9070,
        "output_tokens": 3316,
    }
    base.update(overrides)
    return DiagnosisResult(**base)


# ================================================================
# Caminho feliz: arquivo committado em .observer/reports/ + PR aberto
# ================================================================


class TestCreateReportPrHappyPath:
    def test_calls_create_file_under_observer_reports(self, monkeypatch):
        """create_file deve commitar 1 arquivo em .observer/reports/."""
        provider, fake_repo, _ = _make_provider_and_mocks(monkeypatch)
        diagnosis = _make_diagnosis()

        result = provider.create_report_pr(
            diagnosis,
            failed_task="bronze_ingestion",
            reason="zero_diff",
            cost_usd=0.3847,
        )

        # 1 chamada a create_file com path em .observer/reports/
        assert fake_repo.create_file.call_count == 1
        kwargs = fake_repo.create_file.call_args.kwargs
        assert kwargs["path"].startswith(".observer/reports/")
        assert kwargs["path"].endswith(".md")
        assert "bronze-ingestion" in kwargs["path"]
        assert "zero-diff" in kwargs["path"]
        assert kwargs["branch"].startswith("observer/report-")

        # PR aberto com titulo "report:"
        assert fake_repo.create_pull.call_count == 1
        pull_kwargs = fake_repo.create_pull.call_args.kwargs
        assert pull_kwargs["title"].startswith("report: ")
        assert "bronze_ingestion" in pull_kwargs["title"]
        assert "zero_diff" in pull_kwargs["title"]
        assert pull_kwargs["base"] == "dev"

        # PRResult populado
        assert isinstance(result, PRResult)
        assert result.pr_number == 42
        assert result.pr_url == "https://github.com/owner/repo/pull/42"
        assert result.branch_name.startswith("observer/report-")

    def test_branch_created_from_base_branch(self, monkeypatch):
        """Branch do report sai da base_branch configurada."""
        provider, fake_repo, _ = _make_provider_and_mocks(
            monkeypatch, base_branch="release/v3"
        )
        provider.create_report_pr(
            _make_diagnosis(),
            failed_task="silver_dedup",
            reason="zero_diff",
            cost_usd=0.1,
        )

        # Primeira chamada a get_git_ref pega ref da base_branch
        first_call = fake_repo.get_git_ref.call_args_list[0]
        assert first_call.args[0] == "heads/release/v3"


# ================================================================
# Body do PR carrega os campos do diagnostico
# ================================================================


class TestReportBodyContent:
    def test_body_contains_diagnosis_fields(self, monkeypatch):
        provider, fake_repo, _ = _make_provider_and_mocks(monkeypatch)
        diagnosis = _make_diagnosis(
            diagnosis="ERRO_TEXTO_UNIQUE_A",
            root_cause="CAUSA_TEXTO_UNIQUE_B",
            fix_description="DESC_TEXTO_UNIQUE_C",
            confidence=0.92,
        )

        provider.create_report_pr(
            diagnosis,
            failed_task="bronze_ingestion",
            reason="zero_diff",
            cost_usd=0.3847,
        )

        body = fake_repo.create_pull.call_args.kwargs["body"]
        assert "ERRO_TEXTO_UNIQUE_A" in body
        assert "CAUSA_TEXTO_UNIQUE_B" in body
        assert "DESC_TEXTO_UNIQUE_C" in body
        assert "92%" in body  # confianca formatada
        assert "$0.3847" in body  # custo
        assert "in=9070" in body  # tokens
        assert "out=3316" in body
        assert "bronze_ingestion" in body
        assert "zero_diff" in body
        # Disclaimer no rodape
        assert "Nao ha codigo a aplicar" in body
        assert "workspace do Databricks permanece" in body

    def test_body_explains_reason_zero_diff(self, monkeypatch):
        provider, fake_repo, _ = _make_provider_and_mocks(monkeypatch)
        provider.create_report_pr(
            _make_diagnosis(),
            failed_task="bronze_ingestion",
            reason="zero_diff",
            cost_usd=0.1,
        )
        body = fake_repo.create_pull.call_args.kwargs["body"]
        assert "workspace divergiu da base" in body.lower()
        assert "`dev`" in body  # base_branch interpolada

    def test_body_handles_unknown_reason_gracefully(self, monkeypatch):
        provider, fake_repo, _ = _make_provider_and_mocks(monkeypatch)
        provider.create_report_pr(
            _make_diagnosis(),
            failed_task="bronze_ingestion",
            reason="unknown_reason_xyz",
            cost_usd=0.0,
        )
        body = fake_repo.create_pull.call_args.kwargs["body"]
        # Fallback explanation usado sem crashar
        assert "revisao humana" in body.lower()


# ================================================================
# PII redaction
# ================================================================


class TestReportPiiRedaction:
    def test_cpf_redacted_in_body(self, monkeypatch):
        provider, fake_repo, _ = _make_provider_and_mocks(monkeypatch)
        diagnosis = _make_diagnosis(
            diagnosis="Erro com CPF 123.456.789-01 no payload",
        )
        provider.create_report_pr(
            diagnosis,
            failed_task="bronze_ingestion",
            reason="zero_diff",
            cost_usd=0.1,
        )

        body = fake_repo.create_pull.call_args.kwargs["body"]
        assert "123.456.789-01" not in body
        assert "<REDACTED:CPF>" in body

    def test_phone_redacted_in_body(self, monkeypatch):
        provider, fake_repo, _ = _make_provider_and_mocks(monkeypatch)
        diagnosis = _make_diagnosis(
            root_cause="Mensagem do numero +55 (11) 91234-5678 falhou",
        )
        provider.create_report_pr(
            diagnosis,
            failed_task="bronze_ingestion",
            reason="zero_diff",
            cost_usd=0.1,
        )

        body = fake_repo.create_pull.call_args.kwargs["body"]
        assert "91234-5678" not in body
        assert "<REDACTED:PHONE_BR>" in body


# ================================================================
# Truncamento de payload grande no <details>
# ================================================================


class TestReportPayloadTruncation:
    def test_large_payload_truncated(self, monkeypatch):
        provider, fake_repo, _ = _make_provider_and_mocks(monkeypatch)
        huge_code = "x = 1\n" * 5000  # ~30KB de codigo
        diagnosis = _make_diagnosis(fixed_code=huge_code)
        provider.create_report_pr(
            diagnosis,
            failed_task="bronze_ingestion",
            reason="zero_diff",
            cost_usd=0.1,
        )

        body = fake_repo.create_pull.call_args.kwargs["body"]
        # Body total bem abaixo do limite do GitHub (65_536 bytes)
        assert len(body) < 65_000
        # Marker de truncamento presente
        assert "truncado em" in body

    def test_no_truncation_for_small_payload(self, monkeypatch):
        provider, fake_repo, _ = _make_provider_and_mocks(monkeypatch)
        diagnosis = _make_diagnosis(fixed_code="print('ok')\n")
        provider.create_report_pr(
            diagnosis,
            failed_task="bronze_ingestion",
            reason="zero_diff",
            cost_usd=0.1,
        )

        body = fake_repo.create_pull.call_args.kwargs["body"]
        assert "truncado em" not in body


# ================================================================
# Labels best-effort: falha nao invalida PR
# ================================================================


class TestReportLabels:
    def test_labels_applied_with_confidence_high(self, monkeypatch):
        provider, fake_repo, _ = _make_provider_and_mocks(monkeypatch)
        provider.create_report_pr(
            _make_diagnosis(confidence=0.98),
            failed_task="bronze_ingestion",
            reason="zero_diff",
            cost_usd=0.1,
        )

        # get_issue(pr.number).set_labels(...) chamada
        fake_repo.get_issue.assert_called_once_with(42)
        labels_call = fake_repo.get_issue.return_value.set_labels
        labels_call.assert_called_once()
        labels = labels_call.call_args.args
        assert "observer-report" in labels
        assert "no-code-change" in labels
        assert "confidence-high" in labels

    def test_label_failure_does_not_invalidate_pr(self, monkeypatch):
        provider, fake_repo, _ = _make_provider_and_mocks(monkeypatch)
        # set_labels falha — PR ainda deve ser retornado
        fake_repo.get_issue.return_value.set_labels.side_effect = Exception(
            "404 labels not found"
        )

        result = provider.create_report_pr(
            _make_diagnosis(),
            failed_task="bronze_ingestion",
            reason="zero_diff",
            cost_usd=0.1,
        )

        assert isinstance(result, PRResult)
        assert result.pr_number == 42
        # PR criado mesmo com label falhando
        fake_repo.create_pull.assert_called_once()


# ================================================================
# Protocol default: providers nao-GitHub retornam NotImplementedError
# ================================================================


class TestProtocolDefault:
    def test_base_protocol_raises_not_implemented(self):
        """Outros providers herdando GitProvider sem overrider devem raise."""

        class FakeProvider(GitProvider):
            @property
            def name(self) -> str:
                return "fake"

            def create_fix_pr(self, diagnosis, failed_task):
                raise NotImplementedError

        provider = FakeProvider()
        with pytest.raises(NotImplementedError, match="fake"):
            provider.create_report_pr(
                _make_diagnosis(),
                failed_task="x",
                reason="zero_diff",
                cost_usd=0.0,
            )
