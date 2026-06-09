"""Testes unitarios para o validator pre-PR do Observer."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from observer.validator import (
    ValidationResult,
    _check_notebook_undefined_names,
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
# _check_notebook_undefined_names
# ================================================================


class TestCheckNotebookUndefinedNames:
    def test_returns_none_when_ruff_unavailable(self):
        with patch("observer.validator.subprocess.run", side_effect=FileNotFoundError):
            result = _check_notebook_undefined_names(
                "df = spark.read.table('t')\n", "notebooks/silver/dedup.py"
            )
        assert result is None

    def test_clean_code_returns_ok(self):
        with patch(
            "observer.validator.subprocess.run",
            return_value=type("P", (), {"returncode": 0, "stdout": "", "stderr": ""})(),
        ):
            ok, errors = _check_notebook_undefined_names(
                "df = spark.read.table('t')\n", "notebooks/silver/dedup.py"
            )
        assert ok is True
        assert errors == []

    def test_f821_violation_returned_with_adjusted_line(self):
        import json

        # Preamble tem 16 linhas; erro na linha 17 -> linha 1 do notebook
        violations = [
            {
                "code": "F821",
                "message": "Undefined name `df_inexistente`",
                "location": {"row": 17, "column": 1},
            }
        ]
        mock_proc = type(
            "P",
            (),
            {"returncode": 1, "stdout": json.dumps(violations), "stderr": ""},
        )()
        with patch("observer.validator.subprocess.run", return_value=mock_proc):
            ok, errors = _check_notebook_undefined_names(
                "df_inexistente.drop('x')\n", "notebooks/silver/dedup.py"
            )
        assert ok is False
        assert len(errors) == 1
        assert "F821" in errors[0]
        assert "linha 1" in errors[0]  # 17 - 16 = 1

    def test_preamble_errors_filtered_out(self):
        """Erros em linhas do preamble (row <= 16) sao ignorados."""
        import json

        violations = [
            {
                "code": "F821",
                "message": "Undefined name `x`",
                "location": {"row": 5},  # linha do preamble
            }
        ]
        mock_proc = type(
            "P",
            (),
            {"returncode": 1, "stdout": json.dumps(violations), "stderr": ""},
        )()
        with patch("observer.validator.subprocess.run", return_value=mock_proc):
            ok, errors = _check_notebook_undefined_names(
                "df = spark.read.table('t')\n", "notebooks/silver/dedup.py"
            )
        # Sem erros apos filtrar linhas do preamble
        assert ok is True
        assert errors == []


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
        """Notebook valido passa com syntax + forbidden_imports quando ruff indisponivel."""
        code = (
            "# Databricks notebook source\n"
            "# MAGIC %md\n"
            'print("ola")\n'
        )
        with patch(
            "observer.validator._check_notebook_undefined_names",
            return_value=None,  # ruff nao disponivel
        ):
            result = validate_fix(code, "my_notebooks/bronze/ingest.py")
        assert result.valid is True
        # ruff F821 skipped (None); syntax e forbidden_imports sempre rodam
        assert result.checks_run == ["syntax", "forbidden_imports"]

    def test_notebook_with_undefined_symbol_rejected(self):
        """Notebook com simbolo inexistente e rejeitado via F821."""
        code = (
            "# Databricks notebook source\n"
            "# COMMAND ----------\n"
            "# DBTITLE 1,Transformacoes Low-Code do Pipeline Editor\n"
            "df_parsed = df_inexistente.drop('col_a')\n"
        )
        with patch(
            "observer.validator._check_notebook_undefined_names",
            return_value=(
                False,
                ["ruff F821 (linha 4): Undefined name `df_inexistente`"],
            ),
        ):
            result = validate_fix(code, "notebooks/silver/dedup_clean.py")
        assert result.valid is False
        assert "ruff_f821" in result.checks_run
        assert any("F821" in e for e in result.errors)

    def test_notebook_with_undefined_symbol_ruff_unavailable_passes(self):
        """Sem ruff disponivel, notebook com simbolo indefinido nao e rejeitado."""
        code = (
            "# Databricks notebook source\n"
            "df_parsed = df_inexistente.drop('col_a')\n"
        )
        with patch(
            "observer.validator._check_notebook_undefined_names",
            return_value=None,
        ):
            result = validate_fix(code, "notebooks/silver/dedup_clean.py")
        assert result.valid is True
        assert "ruff_f821" not in result.checks_run

    def test_notebook_with_valid_pyspark_symbols_passes(self):
        """Notebook com codigo PySpark valido passa no check F821."""
        code = (
            "# Databricks notebook source\n"
            "df_bronze = spark.read.table('medallion.bronze.conversations')\n"
            "df_parsed = df_bronze.filter(F.col('x').isNotNull())\n"
        )
        with patch(
            "observer.validator._check_notebook_undefined_names",
            return_value=(True, []),
        ):
            result = validate_fix(code, "notebooks/silver/dedup_clean.py")
        assert result.valid is True
        assert "ruff_f821" in result.checks_run

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

    def test_real_ruff_f821_rejects_notebook_with_undefined_name(self):
        """Smoke C2: ruff real rejeita notebook que referencia variavel inexistente."""
        try:
            import subprocess
            subprocess.run(["ruff", "--version"], capture_output=True, timeout=5)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pytest.skip("ruff nao disponivel")

        # df_inexistente nao e definido em nenhuma linha do notebook
        code = (
            "# Databricks notebook source\n"
            "df_bronze = spark.read.table('medallion.bronze.conversations')\n"
            "\n"
            "# COMMAND ----------\n"
            "\n"
            "# DBTITLE 1,Transformacoes Low-Code do Pipeline Editor\n"
            "df_bronze = df_inexistente.drop('agent_notes')\n"
        )
        result = validate_fix(code, "notebooks/silver/dedup_clean.py")
        assert result.valid is False
        assert "ruff_f821" in result.checks_run
        assert any("F821" in e for e in result.errors)

    def test_real_ruff_f821_accepts_notebook_with_valid_code(self):
        """Smoke C2: ruff real aceita notebook com variaveis corretamente definidas."""
        try:
            import subprocess
            subprocess.run(["ruff", "--version"], capture_output=True, timeout=5)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pytest.skip("ruff nao disponivel")

        # df_bronze e definido antes do bloco gerado, spark/F vem do preamble
        code = (
            "# Databricks notebook source\n"
            "df_bronze = spark.read.table('medallion.bronze.conversations')\n"
            "\n"
            "# COMMAND ----------\n"
            "\n"
            "# DBTITLE 1,Transformacoes Low-Code do Pipeline Editor\n"
            "df_bronze = df_bronze.drop('agent_notes')\n"
        )
        result = validate_fix(code, "notebooks/silver/dedup_clean.py")
        assert result.valid is True
        assert "ruff_f821" in result.checks_run
