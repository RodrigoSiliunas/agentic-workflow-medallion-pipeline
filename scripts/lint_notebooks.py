"""Notebook linter custom (T6 Phase 3).

Ruff exclui `notebooks/` (magics não compilam como Python puro), mas
temos convenções internas que precisam de enforcement:

1. Cell de código deve começar com `# DBTITLE N,title`.
2. `# DBTITLE` não pode aparecer em cell `%md`.
3. Imports só na primeira cell de código.
4. `dbutils.notebook.exit()` não pode estar dentro de `try:`/`except:`.
5. Python em cell deve ter sintaxe válida (`ast.parse`).

Rodar:
    python scripts/lint_notebooks.py path/to/notebooks/**/*.py

Exit code 0 = clean; 1 = violations encontradas.
"""

from __future__ import annotations

import argparse
import ast
import glob
import sys
from dataclasses import dataclass
from pathlib import Path

CELL_SEP = "# COMMAND ----------"


@dataclass
class Violation:
    file: str
    line: int
    rule: str
    message: str

    def format(self) -> str:
        return f"{self.file}:{self.line}: {self.rule}: {self.message}"


def _split_cells(source: str) -> list[tuple[int, list[str]]]:
    """Divide o source em cells. Retorna lista de (line_no_da_primeira_linha, [linhas])."""
    lines = source.splitlines()
    cells: list[tuple[int, list[str]]] = []
    current: list[str] = []
    start_line = 1
    for idx, line in enumerate(lines, start=1):
        if line.strip() == CELL_SEP:
            if current:
                cells.append((start_line, current))
            current = []
            start_line = idx + 1
        else:
            current.append(line)
    if current:
        cells.append((start_line, current))
    return cells


def _is_magic_cell(cell_lines: list[str]) -> bool:
    """True se a cell começa com `# MAGIC %md` ou `# MAGIC %sql`."""
    for line in cell_lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# MAGIC %md") or stripped.startswith("# MAGIC %sql"):
            return True
        if stripped.startswith("# Databricks notebook source"):
            continue  # header
        return False
    return False


def _cell_source(cell_lines: list[str]) -> str:
    return "\n".join(cell_lines)


def _first_nonblank_line(cell_lines: list[str]) -> tuple[int, str] | None:
    for offset, line in enumerate(cell_lines):
        if line.strip():
            return offset, line
    return None


def _check_dbtitle(cell_lines: list[str], start_line: int, file: str) -> list[Violation]:
    violations: list[Violation] = []
    is_magic = _is_magic_cell(cell_lines)
    first = _first_nonblank_line(cell_lines)
    if first is None:
        return violations
    offset, line = first
    stripped = line.strip()

    if is_magic:
        if stripped.startswith("# DBTITLE"):
            violations.append(
                Violation(
                    file=file,
                    line=start_line + offset,
                    rule="NB001",
                    message="DBTITLE não deve aparecer em cell %md",
                )
            )
        return violations

    # Code cell — pula header
    if stripped.startswith("# Databricks notebook source"):
        return violations

    if not stripped.startswith("# DBTITLE"):
        violations.append(
            Violation(
                file=file,
                line=start_line + offset,
                rule="NB002",
                message="Cell de código sem # DBTITLE",
            )
        )
    return violations


def _check_imports_only_first_code_cell(
    cells: list[tuple[int, list[str]]], file: str
) -> list[Violation]:
    violations: list[Violation] = []
    first_code_cell_seen = False
    for start_line, cell_lines in cells:
        if _is_magic_cell(cell_lines):
            continue
        if not any(line.strip() for line in cell_lines):
            continue

        # Parseia a cell pra detectar Import/ImportFrom
        src = _cell_source(cell_lines)
        try:
            tree = ast.parse(src)
        except SyntaxError:
            # Será reportado em _check_syntax; pula aqui
            if not first_code_cell_seen:
                first_code_cell_seen = True
            continue

        # Filtra imports — respeita `# noqa: NB003` na mesma linha
        flagged_imports = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            and not _has_noqa(cell_lines, node.lineno, "NB003")
        ]
        if flagged_imports and first_code_cell_seen:
            violations.append(
                Violation(
                    file=file,
                    line=start_line,
                    rule="NB003",
                    message="Imports devem estar na primeira cell de código",
                )
            )
        if not first_code_cell_seen:
            first_code_cell_seen = True

    return violations


def _has_noqa(cell_lines: list[str], node_line: int, rule: str) -> bool:
    """True se a linha tem `# noqa: <rule>` ou `# noqa` nu."""
    if 1 <= node_line <= len(cell_lines):
        comment = cell_lines[node_line - 1]
        if "# noqa" in comment:
            after = comment.split("# noqa", 1)[1].strip()
            if not after.startswith(":"):
                return True
            rules = [r.strip() for r in after.lstrip(":").split(",")]
            return rule in rules
    return False


def _check_exit_not_in_try(
    cells: list[tuple[int, list[str]]], file: str
) -> list[Violation]:
    violations: list[Violation] = []
    for start_line, cell_lines in cells:
        if _is_magic_cell(cell_lines):
            continue
        src = _cell_source(cell_lines)
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            for child in ast.walk(node):
                if _is_notebook_exit(child):
                    violations.append(
                        Violation(
                            file=file,
                            line=start_line + (child.lineno - 1),
                            rule="NB004",
                            message="dbutils.notebook.exit() dentro de try/except — exit lança exceção especial",
                        )
                    )
    return violations


def _is_notebook_exit(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if (
        isinstance(func, ast.Attribute)
        and func.attr == "exit"
        and isinstance(func.value, ast.Attribute)
        and func.value.attr == "notebook"
        and isinstance(func.value.value, ast.Name)
        and func.value.value.id == "dbutils"
    ):
        return True
    return False


def _check_syntax(
    cells: list[tuple[int, list[str]]], file: str
) -> list[Violation]:
    violations: list[Violation] = []
    for start_line, cell_lines in cells:
        if _is_magic_cell(cell_lines):
            continue
        src = _cell_source(cell_lines)
        if not src.strip():
            continue
        try:
            ast.parse(src)
        except SyntaxError as exc:
            violations.append(
                Violation(
                    file=file,
                    line=start_line + ((exc.lineno or 1) - 1),
                    rule="NB005",
                    message=f"SyntaxError: {exc.msg}",
                )
            )
    return violations


def lint_file(path: str) -> list[Violation]:
    source = Path(path).read_text(encoding="utf-8")
    cells = _split_cells(source)
    violations: list[Violation] = []
    for start_line, cell_lines in cells:
        violations.extend(_check_dbtitle(cell_lines, start_line, path))
    violations.extend(_check_imports_only_first_code_cell(cells, path))
    violations.extend(_check_exit_not_in_try(cells, path))
    violations.extend(_check_syntax(cells, path))
    return violations


def _expand_paths(patterns: list[str]) -> list[str]:
    paths: list[str] = []
    for pattern in patterns:
        matches = glob.glob(pattern, recursive=True)
        if not matches and Path(pattern).is_file():
            matches = [pattern]
        paths.extend(matches)
    return sorted(set(paths))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lint Databricks notebooks (.py format).")
    parser.add_argument(
        "paths",
        nargs="+",
        help="Arquivos ou glob patterns (ex: pipelines/**/notebooks/**/*.py)",
    )
    args = parser.parse_args(argv)

    paths = _expand_paths(args.paths)
    if not paths:
        print("No files matched.", file=sys.stderr)
        return 0

    total_violations = 0
    for path in paths:
        violations = lint_file(path)
        for v in violations:
            print(v.format())
        total_violations += len(violations)

    if total_violations:
        print(f"\n{total_violations} violation(s) em {len(paths)} arquivo(s).", file=sys.stderr)
        return 1
    print(f"OK — {len(paths)} notebook(s) sem violacoes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
