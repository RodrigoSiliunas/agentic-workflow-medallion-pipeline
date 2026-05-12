"""Testes unitarios para multi-file fixes (DiagnosisResult.normalized_fixes e providers)."""

from __future__ import annotations

import json

from observer.providers.base import DiagnosisResult

# ================================================================
# DiagnosisResult.normalized_fixes
# ================================================================


class TestNormalizedFixes:
    def test_singular_fallback(self):
        """Quando so ha fixed_code/file_to_fix, retorna lista com 1 elemento."""
        result = DiagnosisResult(
            fixed_code="print('ok')",
            file_to_fix="pipeline/notebooks/bronze/ingest.py",
        )
        fixes = result.normalized_fixes()
        assert len(fixes) == 1
        assert fixes[0]["file_path"] == "pipeline/notebooks/bronze/ingest.py"
        assert fixes[0]["code"] == "print('ok')"

    def test_multi_file_preferred_over_singular(self):
        """Quando fixes tem entradas validas, ignora fixed_code/file_to_fix."""
        result = DiagnosisResult(
            fixed_code="# singular (deve ser ignorado)",
            file_to_fix="a.py",
            fixes=[
                {"file_path": "src/schema/contracts.py", "code": "X"},
                {"file_path": "pipeline/notebooks/bronze/ingest.py", "code": "Y"},
            ],
        )
        fixes = result.normalized_fixes()
        assert len(fixes) == 2
        assert [f["file_path"] for f in fixes] == [
            "src/schema/contracts.py",
            "pipeline/notebooks/bronze/ingest.py",
        ]
        assert fixes[0]["code"] == "X"
        assert fixes[1]["code"] == "Y"

    def test_empty_fixes_falls_back_to_singular(self):
        """fixes=[] mas fixed_code preenchido -> fallback."""
        result = DiagnosisResult(
            fixed_code="print('ok')",
            file_to_fix="a.py",
            fixes=[],
        )
        fixes = result.normalized_fixes()
        assert len(fixes) == 1
        assert fixes[0]["file_path"] == "a.py"

    def test_fixes_with_invalid_entries_filtered(self):
        """Entradas vazias ou sem campos obrigatorios sao filtradas."""
        result = DiagnosisResult(
            fixes=[
                {"file_path": "a.py", "code": "codigo A"},
                {"file_path": "", "code": "sem path"},
                {"file_path": "b.py", "code": ""},
                {"file_path": "c.py", "code": "codigo C"},
                "nao eh dict",
                {"code": "sem file_path"},
            ]
        )
        fixes = result.normalized_fixes()
        assert len(fixes) == 2
        assert [f["file_path"] for f in fixes] == ["a.py", "c.py"]

    def test_all_fixes_invalid_falls_back_to_singular(self):
        """Se todas as entradas de fixes sao invalidas, usa singular."""
        result = DiagnosisResult(
            fixed_code="singular code",
            file_to_fix="singular.py",
            fixes=[{"file_path": "", "code": ""}],
        )
        fixes = result.normalized_fixes()
        assert len(fixes) == 1
        assert fixes[0]["file_path"] == "singular.py"

    def test_empty_everything_returns_empty_list(self):
        result = DiagnosisResult()
        assert result.normalized_fixes() == []

    def test_only_fixed_code_without_file_to_fix_returns_empty(self):
        result = DiagnosisResult(fixed_code="print('ok')", file_to_fix=None)
        assert result.normalized_fixes() == []

    def test_only_file_to_fix_without_fixed_code_returns_empty(self):
        result = DiagnosisResult(fixed_code=None, file_to_fix="a.py")
        assert result.normalized_fixes() == []

    def test_file_path_stripped(self):
        result = DiagnosisResult(
            fixes=[{"file_path": "  a.py  ", "code": "code"}]
        )
        fixes = result.normalized_fixes()
        assert fixes[0]["file_path"] == "a.py"


# ================================================================
# to_dict inclui fixes
# ================================================================


class TestToDictIncludesFixes:
    def test_to_dict_includes_fixes_field(self):
        result = DiagnosisResult(
            fixes=[{"file_path": "a.py", "code": "X"}]
        )
        d = result.to_dict()
        assert "fixes" in d
        assert d["fixes"] == [{"file_path": "a.py", "code": "X"}]

    def test_to_dict_fixes_none_when_not_set(self):
        result = DiagnosisResult(fixed_code="x", file_to_fix="a.py")
        d = result.to_dict()
        assert d["fixes"] is None


# ================================================================
# Anthropic _parse_json passa fixes adiante
# ================================================================


class TestAnthropicParse:
    def test_parse_json_with_fixes_array(self):
        from observer.providers.anthropic_provider import (
            AnthropicProvider,
        )

        provider = AnthropicProvider(api_key="", model="test")
        payload = json.dumps(
            {
                "diagnosis": "bug",
                "root_cause": "x",
                "fix_description": "y",
                "fixes": [
                    {"file_path": "a.py", "code": "A"},
                    {"file_path": "b.py", "code": "B"},
                ],
                "confidence": 0.9,
                "requires_human_review": False,
            }
        )
        data = provider._parse_json(payload)
        assert data["fixes"][0]["file_path"] == "a.py"
        assert len(data["fixes"]) == 2


# ================================================================
# Simulacao de uso pelo GitHubProvider (sem PyGithub real)
# ================================================================


class TestGitHubProviderValidation:
    def test_create_fix_pr_rejects_empty_diagnosis(self):
        """create_fix_pr deve rejeitar DiagnosisResult sem fixes aplicaveis."""
        import pytest

        from observer.providers.github_provider import GitHubProvider

        provider = GitHubProvider(token="fake", repo="owner/repo")
        empty = DiagnosisResult()  # sem fixes nem singular

        with pytest.raises(ValueError, match="nao contem fixes"):
            provider.create_fix_pr(empty, "bronze_ingestion")


class TestGitHubProviderBranchBase:
    """Branch deve ser criada a partir do base_branch (PR target), nao
    de "main" hardcoded. Antes da correcao, criava sempre de main
    mesmo quando o PR ia pra dev — gerava diff espurio se dev divergiu.
    """

    def _make_provider_and_mocks(self, monkeypatch, base_branch):
        from unittest.mock import MagicMock

        from observer.providers.github_provider import GitHubProvider

        fake_pygithub = MagicMock()
        fake_repo = MagicMock()
        fake_ref = MagicMock()
        fake_ref.object.sha = "deadbeefcafe"
        fake_repo.get_git_ref.return_value = fake_ref
        # get_contents devolve um stub valido — passa pelos guards de
        # path-exists e do update_file (sha extraido daqui).
        fake_contents = MagicMock()
        fake_contents.sha = "filebeef"
        fake_repo.get_contents.return_value = fake_contents
        # Mock compare() para devolver diff nao-vazio (passa pelo guard
        # de zero-diff). Cada teste foca em algo diferente do diff em si.
        fake_compare = MagicMock()
        fake_compare.files = [MagicMock()]
        fake_repo.compare.return_value = fake_compare
        fake_pygithub.return_value.get_repo.return_value = fake_repo

        # Mock do modulo github importado lazy dentro de create_fix_pr
        import sys
        import types

        fake_module = types.ModuleType("github")
        fake_module.Github = fake_pygithub
        fake_module.Auth = MagicMock()
        monkeypatch.setitem(sys.modules, "github", fake_module)

        provider = GitHubProvider(
            token="fake", repo="owner/repo", base_branch=base_branch
        )
        return provider, fake_repo

    def test_branch_created_from_base_branch_dev(self, monkeypatch):
        provider, fake_repo = self._make_provider_and_mocks(monkeypatch, "dev")

        result = DiagnosisResult(
            fixed_code="print('ok')",
            file_to_fix="pipelines/pipeline-seguradora-whatsapp/notebooks/bronze/ingest.py",
            confidence=0.9,
        )

        provider.create_fix_pr(result, "bronze_ingestion")

        # Primeira chamada de get_git_ref deve ser para heads/dev
        first_call = fake_repo.get_git_ref.call_args_list[0]
        assert first_call.args[0] == "heads/dev", (
            f"Branch deve sair de heads/dev mas saiu de {first_call.args[0]}"
        )

    def test_branch_created_from_base_branch_custom(self, monkeypatch):
        provider, fake_repo = self._make_provider_and_mocks(
            monkeypatch, "release/v2"
        )

        result = DiagnosisResult(
            fixed_code="print('ok')",
            file_to_fix="pipelines/pipeline-seguradora-whatsapp/notebooks/bronze/ingest.py",
            confidence=0.9,
        )

        provider.create_fix_pr(result, "silver_dedup")

        first_call = fake_repo.get_git_ref.call_args_list[0]
        assert first_call.args[0] == "heads/release/v2"

    def test_create_fix_pr_raises_when_path_doesnt_exist(self, monkeypatch):
        """LLM propondo path inventado (ex: /pipeline/ extra) deve ser
        rejeitado antes de criar branch — evita PR com arquivo fantasma.
        """
        import pytest

        provider, fake_repo = self._make_provider_and_mocks(monkeypatch, "dev")
        # Simula path nao existente na base
        fake_repo.get_contents.side_effect = Exception("404 not found")

        result = DiagnosisResult(
            fixed_code="print('ok')",
            file_to_fix="pipelines/pipeline-seguradora-whatsapp/pipeline/notebooks/bronze/ingest.py",
            confidence=0.9,
        )

        with pytest.raises(ValueError, match="nao existem em dev"):
            provider.create_fix_pr(result, "bronze_ingestion")

        # Branch nunca foi criada
        fake_repo.create_git_ref.assert_not_called()
        fake_repo.create_pull.assert_not_called()

    def test_create_fix_pr_raises_when_diff_is_empty(self, monkeypatch):
        """Se compare() retorna files=[] o LLM propos conteudo identico
        a base — nao abrir PR vazio.
        """
        import pytest

        provider, fake_repo = self._make_provider_and_mocks(monkeypatch, "dev")
        # Zera o diff retornado pelo compare()
        fake_repo.compare.return_value.files = []

        result = DiagnosisResult(
            fixed_code="print('ok')",
            file_to_fix="pipelines/pipeline-seguradora-whatsapp/notebooks/bronze/ingest.py",
            confidence=0.9,
        )

        with pytest.raises(ValueError, match="identico a dev"):
            provider.create_fix_pr(result, "bronze_ingestion")

        # PR nunca chega a ser criado
        fake_repo.create_pull.assert_not_called()
