"""Testes unitarios para o validator pre-PR do Observer."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from observer.validator import (
    ValidationResult,
    _check_syntax,
    _parse_ruff_json,
    _should_run_ruff,
    validate_fix,
)

# ================================================================
# _check_syntax
# ================================================================


class TestCheckSyntax:
    def test_valid_code_returns_empty(self):
        code = "def foo():\n    return 1 + 2\n"
        assert _check_syntax(code, "foo.py") == []

    def test_syntax_error_returns_message(self):
        code = "def foo(\n    return 1\n"
        errors = _check_syntax(code, "foo.py")
        assert len(errors) == 1
        assert "SyntaxError" in errors[0]

    def test_notebook_with_magics_is_valid(self):
        """Databricks notebooks com # MAGIC sao comentarios — compile aceita."""
        code = (
            "# Databricks notebook source\n"
            "# MAGIC %md\n"
            "# MAGIC # Titulo\n"
            "# COMMAND ----------\n"
            "# DBTITLE 1,Nome\n"
            "import sys\n"
            'print("ola")\n'
        )
        assert _check_syntax(code, "my_notebooks/bronze/ingest.py") == []

    def test_indentation_error_detected(self):
        code = "def foo():\nreturn 1\n"
        errors = _check_syntax(code, "foo.py")
        assert len(errors) == 1
        assert "SyntaxError" in errors[0] or "IndentationError" in errors[0]

    def test_unclosed_string_detected(self):
        code = 'msg = "unclosed\n'
        errors = _check_syntax(code, "foo.py")
        assert errors  # algum erro reportado


# ================================================================
# _should_run_ruff
# ================================================================


class TestShouldRunRuff:
    def test_non_notebook_file_runs_ruff(self):
        assert _should_run_ruff("src/storage/s3_client.py") is True

    def test_notebook_file_skips_ruff(self):
        assert _should_run_ruff("my_notebooks/bronze/ingest.py") is False

    def test_deploy_script_runs_ruff(self):
        assert _should_run_ruff("src/deploy/create_workflow.py") is True

    def test_non_python_file_skips_ruff(self):
        assert _should_run_ruff("observer_config.yaml") is False

    def test_empty_path_skips_ruff(self):
        assert _should_run_ruff("") is False

    def test_windows_path_separator(self):
        assert _should_run_ruff("my_project\\notebooks\\bronze\\ingest.py") is False
        assert _should_run_ruff("my_project\\src\\foo.py") is True


# ================================================================
# _parse_ruff_json
# ================================================================


class TestParseRuffJson:
    def test_empty_stdout_returns_empty(self):
        assert _parse_ruff_json("") == []
        assert _parse_ruff_json("   ") == []

    def test_valid_json_produces_messages(self):
        stdout = (
            '[{"code": "E501", "message": "line too long",'
            ' "location": {"row": 42, "column": 10}}]'
        )
        messages = _parse_ruff_json(stdout)
        assert len(messages) == 1
        assert "E501" in messages[0]
        assert "linha 42" in messages[0]
        assert "line too long" in messages[0]

    def test_multiple_violations(self):
        stdout = (
            '[{"code": "E501", "message": "line too long", "location": {"row": 1}},'
            '{"code": "F401", "message": "unused import", "location": {"row": 5}}]'
        )
        messages = _parse_ruff_json(stdout)
        assert len(messages) == 2

    def test_invalid_json_returns_raw(self):
        messages = _parse_ruff_json("not json at all")
        assert len(messages) == 1
        assert "ruff" in messages[0]


# ================================================================
# validate_fix (integration)
# ================================================================


class TestValidateFix:
    def test_empty_code_rejected(self):
        result = validate_fix("", "foo.py")
        assert result.valid is False
        assert "vazio" in result.errors[0]

    def test_whitespace_code_rejected(self):
        result = validate_fix("   \n\t\n", "foo.py")
        assert result.valid is False

    def test_syntax_error_rejected(self):
        result = validate_fix("def foo(:\n    pass", "foo.py")
        assert result.valid is False
        assert "syntax" in result.checks_run
        # Ruff nao roda quando syntax falha
        assert "ruff" not in result.checks_run

    def test_valid_notebook_passes_without_ruff(self):
        """Notebook valido passa com syntax + forbidden_imports (sem ruff)."""
        code = (
            "# Databricks notebook source\n"
            "# MAGIC %md\n"
            'print("ola")\n'
        )
        result = validate_fix(code, "my_notebooks/bronze/ingest.py")
        assert result.valid is True
        # ruff pulado em notebooks; syntax e forbidden_imports sempre rodam
        assert result.checks_run == ["syntax", "forbidden_imports"]

    def test_non_notebook_without_ruff_still_validates_syntax(self):
        """Sem ruff instalado, o resultado depende so de syntax."""
        code = "def foo():\n    return 1\n"

        with patch(
            "observer.validator._run_ruff",
            return_value=None,
        ):
            result = validate_fix(code, "src/foo.py")

        assert result.valid is True
        assert "syntax" in result.checks_run
        # ruff nao foi contabilizado porque retornou None (indisponivel)
        assert "ruff" not in result.checks_run

    def test_non_notebook_with_ruff_ok(self):
        code = "def foo():\n    return 1\n"
        with patch(
            "observer.validator._run_ruff",
            return_value=(True, []),
        ):
            result = validate_fix(code, "src/foo.py")

        assert result.valid is True
        assert "syntax" in result.checks_run
        assert "ruff" in result.checks_run

    def test_non_notebook_with_ruff_errors(self):
        code = "def foo():\n    return 1\n"
        with patch(
            "observer.validator._run_ruff",
            return_value=(False, ["ruff E501 (linha 1): line too long"]),
        ):
            result = validate_fix(code, "src/foo.py")

        assert result.valid is False
        assert "syntax" in result.checks_run
        assert "ruff" in result.checks_run
        assert any("E501" in e for e in result.errors)


# ================================================================
# ValidationResult helpers
# ================================================================


class TestValidationResult:
    def test_default_is_valid(self):
        r = ValidationResult()
        assert r.valid is True
        assert r.errors == []
        assert r.checks_run == []

    def test_add_error_flips_valid(self):
        r = ValidationResult()
        r.add_error("boom")
        assert r.valid is False
        assert r.errors == ["boom"]

    def test_multiple_errors_accumulate(self):
        r = ValidationResult()
        r.add_error("a")
        r.add_error("b")
        assert r.errors == ["a", "b"]
        assert r.valid is False


# ================================================================
# Smoke test: integra com ruff real se disponivel
# ================================================================


class TestRuffSmoke:
    """Testa que ruff real funciona no validator se estiver disponivel."""

    def test_real_ruff_on_clean_code(self):
        """Executa ruff real (se disponivel) em codigo limpo."""
        try:
            import subprocess
            subprocess.run(
                ["ruff", "--version"], capture_output=True, timeout=5
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pytest.skip("ruff nao disponivel")

        code = (
            '"""Modulo de teste."""\n'
            "\n"
            "\n"
            "def soma(a: int, b: int) -> int:\n"
            '    """Soma dois inteiros."""\n'
            "    return a + b\n"
        )
        result = validate_fix(code, "src/soma.py")
        assert result.valid is True
        assert "syntax" in result.checks_run
        assert "ruff" in result.checks_run
