"""Validacao pre-PR dos fixes gerados pelo LLM.

Antes de abrir um PR com um fix proposto pelo Observer, roda:

  1. Validacao sintatica via `compile` + `ast.parse` (sempre, barata)
  2. `ruff check` via subprocess (apenas para arquivos `.py` fora de
     diretorios `notebooks/`, porque notebooks Databricks tem magics
     que ruff reportaria como erro)

Se qualquer check falha, o Observer marca o diagnostico como
`status='validation_failed'` e NAO cria o PR.

Uso:
    from observer import validate_fix

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

# Imports e chamadas proibidas em fixes do LLM.
# Motivo: um prompt injection bem-sucedido poderia propor fix com
# shell exec / network custom / eval dinâmico. Barramos aqui mesmo
# que sintaxe + ruff passem.
FORBIDDEN_IMPORTS: frozenset[str] = frozenset(
    {
        "subprocess",
        "socket",
        "ctypes",
        "pty",
        "pickle",
        "marshal",
        "shutil",  # rm -rf / copytree em paths arbitrários
    }
)

# Atributos compostos proibidos (ex: os.system, os.popen).
FORBIDDEN_ATTR_CALLS: frozenset[tuple[str, str]] = frozenset(
    {
        ("os", "system"),
        ("os", "popen"),
        ("os", "execv"),
        ("os", "execvp"),
        ("os", "_exit"),
        ("os", "remove"),
        ("os", "unlink"),
        ("os", "rmdir"),
    }
)

FORBIDDEN_BUILTIN_CALLS: frozenset[str] = frozenset(
    {
        "eval",
        "exec",
        "compile",
        "__import__",
    }
)


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


def _check_forbidden_imports(code: str, file_path: str) -> list[str]:
    """Detecta imports e chamadas banidas em fixes do LLM.

    Roda após o syntax check (precisa de AST válida). Escaneia:
    - `import X`  / `from X import Y`   → valida nomes raiz contra FORBIDDEN_IMPORTS
    - `os.system(...)` etc.             → FORBIDDEN_ATTR_CALLS
    - `eval(...)` / `exec(...)` / `__import__(...)` → FORBIDDEN_BUILTIN_CALLS

    Observer exempted de si mesmo: se o fix é em `observer/validator.py`
    (o arquivo atual), não bloqueia porque o próprio módulo precisa
    declarar o conjunto proibido.
    """
    errors: list[str] = []

    # Fix do próprio validator pode mencionar os nomes banidos em listas
    # constantes. Ficaria no caminho da própria ferramenta.
    normalized = (file_path or "").replace("\\", "/")
    if normalized.endswith("observer/validator.py"):
        return errors

    try:
        tree = ast.parse(code, filename=file_path or "<fix>")
    except SyntaxError:
        # _check_syntax já reportou — sem mais nada a fazer aqui.
        return errors

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root in FORBIDDEN_IMPORTS:
                    errors.append(
                        f"import proibido '{alias.name}' (linha {node.lineno})"
                    )
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".", 1)[0]
            if root in FORBIDDEN_IMPORTS:
                errors.append(
                    f"from-import proibido '{node.module}' (linha {node.lineno})"
                )
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in FORBIDDEN_BUILTIN_CALLS:
                errors.append(
                    f"chamada proibida '{func.id}()' (linha {node.lineno})"
                )
            elif (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and (func.value.id, func.attr) in FORBIDDEN_ATTR_CALLS
            ):
                errors.append(
                    f"chamada proibida '{func.value.id}.{func.attr}()' "
                    f"(linha {node.lineno})"
                )

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
            # Validador foca em CORRETUDE, nao estilo. Pyflakes (F) cobre:
            # nomes indefinidos, imports nao usados, variaveis redefinidas,
            # erros logicos. Estilo (I=isort, N=naming, E=pycodestyle, etc)
            # rejeitaria fixes do agente que sao logicamente corretos mas
            # divergem da convencao do projeto — ruim pra DX do agente.
            # `--isolated` ignora pyproject.toml, garante mesmo
            # comportamento independente de cwd (test, CI ou Databricks).
            proc = subprocess.run(  # noqa: S603 — subprocess controlado
                [
                    "ruff", "check", "--isolated",
                    "--select", "F",
                    "--output-format=json", temp_path,
                ],
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
            (ex: `observer/persistence.py` ou `src/my_module.py`).

    Returns:
        ValidationResult com `valid`, `errors` e `checks_run`.
    """
    result = ValidationResult()

    if not code or not code.strip():
        result.add_error("fix vazio")
        return result

    # 1) Syntax check (Python apenas — YAML/JSON/TOML usam parsers proprios)
    if file_path.endswith(".yaml") or file_path.endswith(".yml"):
        result.checks_run.append("yaml")
        try:
            import yaml as _yaml
            _yaml.safe_load(code)
        except Exception as exc:  # noqa: BLE001
            result.add_error(f"YAMLError: {exc}")
    elif file_path.endswith(".json"):
        result.checks_run.append("json")
        try:
            import json as _json
            _json.loads(code)
        except Exception as exc:  # noqa: BLE001
            result.add_error(f"JSONError: {exc}")
    else:
        result.checks_run.append("syntax")
        for err in _check_syntax(code, file_path):
            result.add_error(err)

    # Se a sintaxe ja falhou, nao vale rodar ruff
    if not result.valid:
        return result

    # Non-Python: skip Python-specific checks (forbidden imports, ruff)
    if not file_path.endswith(".py"):
        return result

    # 2) Import/call allowlist (sempre, depois de sintaxe valida)
    result.checks_run.append("forbidden_imports")
    for err in _check_forbidden_imports(code, file_path):
        result.add_error(err)

    # Se ja detectamos import banido, nao vale rodar ruff — o fix sera
    # rejeitado de qualquer jeito e ruff pode ser lento em arquivo grande.
    if not result.valid:
        return result

    # 3) Ruff check (condicional)
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
