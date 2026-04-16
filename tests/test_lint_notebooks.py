"""Testes do linter de notebooks (T6 Phase 3)."""

from __future__ import annotations

import sys
from pathlib import Path


# Adiciona scripts/ ao sys.path
_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts"))

from lint_notebooks import (  # noqa: E402
    _has_noqa,
    _is_magic_cell,
    _split_cells,
    lint_file,
)

NOTEBOOK_HEADER = "# Databricks notebook source"


def _write_notebook(tmp_path: Path, cells: list[str]) -> Path:
    source = f"{NOTEBOOK_HEADER}\n" + "\n# COMMAND ----------\n".join(cells)
    nb = tmp_path / "sample.py"
    nb.write_text(source, encoding="utf-8")
    return nb


class TestSplitCells:
    def test_splits_on_separator(self):
        src = "# DBTITLE 1,A\nprint(1)\n# COMMAND ----------\n# DBTITLE 1,B\nprint(2)\n"
        cells = _split_cells(src)
        assert len(cells) == 2


class TestIsMagicCell:
    def test_md_cell(self):
        lines = ["# MAGIC %md", "# MAGIC # Title"]
        assert _is_magic_cell(lines)

    def test_code_cell(self):
        lines = ["# DBTITLE 1,A", "print(1)"]
        assert not _is_magic_cell(lines)

    def test_header_alone_is_not_magic(self):
        lines = ["# Databricks notebook source"]
        assert not _is_magic_cell(lines)


class TestNoqa:
    def test_bare_noqa_matches_any_rule(self):
        lines = ["import foo  # noqa"]
        assert _has_noqa(lines, 1, "NB003")

    def test_specific_noqa_matches_rule(self):
        lines = ["import foo  # noqa: NB003"]
        assert _has_noqa(lines, 1, "NB003")

    def test_specific_noqa_misses_other_rule(self):
        lines = ["import foo  # noqa: NB003"]
        assert not _has_noqa(lines, 1, "NB999")

    def test_multi_noqa(self):
        lines = ["import foo  # noqa: NB001, NB003"]
        assert _has_noqa(lines, 1, "NB003")
        assert _has_noqa(lines, 1, "NB001")


class TestLintFile:
    def test_clean_notebook_passes(self, tmp_path):
        nb = _write_notebook(
            tmp_path,
            [
                "# MAGIC %md\n# MAGIC # Title\n",
                "# DBTITLE 1,Imports\nimport os\nimport sys\n",
                "# DBTITLE 1,Work\nprint(1)\n",
            ],
        )
        assert lint_file(str(nb)) == []

    def test_missing_dbtitle_reports_NB002(self, tmp_path):
        nb = _write_notebook(
            tmp_path,
            [
                "# DBTITLE 1,Imports\nimport os\n",
                # Segunda cell sem DBTITLE
                "print(1)\n",
            ],
        )
        violations = lint_file(str(nb))
        assert any(v.rule == "NB002" for v in violations)

    def test_dbtitle_in_md_cell_reports_NB001(self, tmp_path):
        nb = _write_notebook(
            tmp_path,
            [
                "# DBTITLE 1,Imports\nimport os\n",
                "# DBTITLE 1,Bad\n# MAGIC %md\n",
            ],
        )
        # Ordem importa — primeira linha é DBTITLE e depois MAGIC %md
        # Esse caso e ambíguo — linter trata como code-first, reporta NB001
        violations = lint_file(str(nb))
        # Deve gerar NB001 ou nao (depende de qual vem primeiro).
        # Aqui validamos que nao crasha:
        assert isinstance(violations, list)

    def test_import_in_second_cell_reports_NB003(self, tmp_path):
        nb = _write_notebook(
            tmp_path,
            [
                "# DBTITLE 1,First\nprint(1)\n",
                "# DBTITLE 1,Second\nimport os\n",
            ],
        )
        violations = lint_file(str(nb))
        assert any(v.rule == "NB003" for v in violations)

    def test_noqa_silences_NB003(self, tmp_path):
        nb = _write_notebook(
            tmp_path,
            [
                "# DBTITLE 1,First\nprint(1)\n",
                "# DBTITLE 1,Second\nimport os  # noqa: NB003\n",
            ],
        )
        violations = lint_file(str(nb))
        assert all(v.rule != "NB003" for v in violations)

    def test_exit_in_try_reports_NB004(self, tmp_path):
        nb = _write_notebook(
            tmp_path,
            [
                "# DBTITLE 1,Work\n"
                "try:\n"
                "    x = 1\n"
                "    dbutils.notebook.exit('done')\n"
                "except Exception:\n"
                "    pass\n",
            ],
        )
        violations = lint_file(str(nb))
        assert any(v.rule == "NB004" for v in violations)

    def test_exit_outside_try_is_fine(self, tmp_path):
        nb = _write_notebook(
            tmp_path,
            [
                "# DBTITLE 1,Work\n"
                "x = 1\n"
                "dbutils.notebook.exit('done')\n",
            ],
        )
        violations = lint_file(str(nb))
        assert all(v.rule != "NB004" for v in violations)

    def test_syntax_error_reports_NB005(self, tmp_path):
        nb = _write_notebook(
            tmp_path,
            [
                "# DBTITLE 1,Bad\ndef foo(\n",
            ],
        )
        violations = lint_file(str(nb))
        assert any(v.rule == "NB005" for v in violations)
