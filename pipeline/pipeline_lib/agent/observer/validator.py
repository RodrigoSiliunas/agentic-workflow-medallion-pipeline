"""Validacao pre-PR dos fixes gerados pelo LLM.

Antes de abrir um PR com um fix proposto pelo Observer, roda:

  1. Validacao sintatica via `compile` + `ast.parse` (sempre, barata)
  2. `ruff check` via subprocess (apenas para arquivos em pipeline_lib/,
     porque notebooks Databricks tem magics que ruff reportaria como erro)

Se qualquer check falha, o Observer marca o diagnostico como
`status='validation_failed'` e NAO cria o PR.

Uso:
    from pipeline_lib.agent.observer import validate_fix

    result = validate_fix(
        code=diagnosis.fixed_code,
        file_path=diagnosis.file_to_fix,
    )
    if not result.valid:
        log.append(f"Fix rejeitado: {result.errors}")
        return
"""

from __future__ import annotations

import ast
import contextlib
import json
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

RUFF_TIMEOUT_SECONDS = 30


@dataclass
class ValidationResult:
    """Resultado da validacao pre-PR de um fix.

    valid: True se todos os checks executados passaram.
    errors: lista de mensagens (vazia quando valid=True).
    checks_run: quais checks foram executados (syntax sempre, ruff condicional).
    """

    valid: bool = True
    errors: list[str] = field(default_factory=list)
    checks_run: list[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        self.errors.append(message)
        self.valid = False


def _check_syntax(code: str, file_path: str) -> list[str]:
    """Valida sintaxe Python via compile + ast.parse.

    Notebooks Databricks com magics (`# MAGIC %md`, `# COMMAND ----------`)
    passam porque sao comentarios do ponto de vista do parser Python.

    Retorna lista vazia se OK, ou lista com mensagens de erro.
    """
    errors: list[str] = []

    try:
        compile(code, file_path or "<fix>", "exec")
    except SyntaxError as exc:
        line = exc.lineno or "?"
        errors.append(f"SyntaxError (linha {line}): {exc.msg}")
        return errors  # Sem sentido tentar AST se compile ja falhou

    try:
        ast.parse(code, filename=file_path or "<fix>")
    except SyntaxError as exc:
        line = exc.lineno or "?"
        errors.append(f"ast.parse falhou (linha {line}): {exc.msg}")

    return errors


def _should_run_ruff(file_path: str) -> bool:
    """Decide se ruff deve rodar para o arquivo em questao.

    Regras:
    - `pipeline/notebooks/` eh excluido do ruff no projeto (pyproject.toml),
      entao nao rodamos ruff em notebooks Databricks.
    - `.py` em qualquer outro lugar do projeto roda ruff.
    - Extensoes nao-Python nunca rodam ruff.
    """
    if not file_path:
        return False
    normalized = file_path.replace("\\", "/").lower()
    if not normalized.endswith(".py"):
        return False
    return "notebooks/" not in normalized


def _parse_ruff_json(stdout: str) -> list[str]:
    """Converte a saida JSON do ruff em mensagens legiveis."""
    if not stdout.strip():
        return []
    try:
        violations = json.loads(stdout)
    except json.JSONDecodeError:
        return [f"ruff: saida nao-JSON: {stdout[:200]}"]

    if not isinstance(violations, list):
        return [f"ruff: formato JSON inesperado: {stdout[:200]}"]

    messages: list[str] = []
    for v in violations:
        code = v.get("code") or "?"
        msg = v.get("message") or ""
        location = v.get("location") or {}
        row = location.get("row", "?")
        messages.append(f"ruff {code} (linha {row}): {msg}")
    return messages


def _run_ruff(code: str, file_path: str) -> tuple[bool, list[str]] | None:
    """Roda `ruff check --output-format=json` no fix via arquivo temporario.

    Retorna:
      None  -> ruff nao disponivel (subprocess falhou com FileNotFoundError);
               o validator faz skip gracefully.
      (True, [])         -> ruff executou e nao encontrou problemas.
      (False, [...])     -> ruff executou e encontrou violacoes.
    """
    temp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            suffix=".py",
            mode="w",
            delete=False,
            encoding="utf-8",
        ) as handle:
            handle.write(code)
            temp_path = handle.name

        try:
            proc = subprocess.run(  # noqa: S603 — subprocess controlado
                ["ruff", "check", "--output-format=json", temp_path],
                capture_output=True,
                text=True,
                timeout=RUFF_TIMEOUT_SECONDS,
            )
        except FileNotFoundError:
            # ruff nao instalado no runtime (ex: Databricks cluster base)
            return None
        except subprocess.TimeoutExpired:
            return (False, [f"ruff: timeout apos {RUFF_TIMEOUT_SECONDS}s"])

        if proc.returncode == 0:
            return (True, [])

        errors = _parse_ruff_json(proc.stdout)
        if not errors:
            # returncode != 0 mas sem violacoes JSON — erro de execucao
            stderr = (proc.stderr or "").strip()
            errors = [f"ruff retornou {proc.returncode}: {stderr[:200]}"]
        return (False, errors)

    finally:
        if temp_path and os.path.exists(temp_path):
            with contextlib.suppress(OSError):
                os.unlink(temp_path)


def validate_fix(code: str, file_path: str) -> ValidationResult:
    """Valida um fix proposto pelo LLM antes de abrir PR.

    Sempre roda `_check_syntax`. Roda `ruff` apenas para arquivos fora de
    `notebooks/` (notebooks Databricks sao excluidos do lint no projeto).

    Args:
        code: codigo Python completo do fix proposto.
        file_path: caminho relativo do arquivo que sera substituido
            (ex: `pipeline/pipeline_lib/storage/s3_client.py`).

    Returns:
        ValidationResult com `valid`, `errors` e `checks_run`.
    """
    result = ValidationResult()

    if not code or not code.strip():
        result.add_error("fix vazio")
        return result

    # 1) Syntax check (sempre)
    result.checks_run.append("syntax")
    for err in _check_syntax(code, file_path):
        result.add_error(err)

    # Se a sintaxe ja falhou, nao vale rodar ruff
    if not result.valid:
        return result

    # 2) Ruff check (condicional)
    if _should_run_ruff(file_path):
        ruff_outcome = _run_ruff(code, file_path)
        if ruff_outcome is None:
            logger.info("ruff nao disponivel — skip do check de lint")
        else:
            result.checks_run.append("ruff")
            ok, errors = ruff_outcome
            if not ok:
                for err in errors:
                    result.add_error(err)

    return result
