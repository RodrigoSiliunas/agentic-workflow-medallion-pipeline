"""Allowlist de paths para commits do Observer Agent.

Limita o escopo do que o LLM pode modificar via GitProvider. Evita que
um prompt injection leve o agente a escrever em `.github/`, `infra/` ou
qualquer caminho com `secret` no nome.
"""

from __future__ import annotations

import re

# Paths permitidos (prefixos). Qualquer arquivo fora destes prefixos é
# rejeitado pelo GitProvider antes do commit.
# Observer NAO escreve nele mesmo (observer-framework/observer/) — auto-modify
# permitiria prompt injection esvaziar o validador no proximo run.
ALLOWED_PATH_PREFIXES: tuple[str, ...] = (
    "pipelines/",
    "observer-framework/tests/",
    "platform/backend/app/",
    "platform/backend/tests/",
    "platform/frontend/app/",
    "platform/frontend/tests/",
)

# Padrões sempre negados, mesmo se o prefixo pareça permitido.
DENIED_PATH_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?:^|/)\.github(?:/|$)"),
    re.compile(r"(?:^|/)\.git(?:/|$)"),
    re.compile(r"(?:^|/)infra(?:/|$)"),
    re.compile(r"(?:^|/)deploy(?:/|$)"),
    re.compile(r"(?:^|/)terraform(?:/|$)"),
    re.compile(r"(?:^|/)(?:[^/]*secret[^/]*)", re.IGNORECASE),
    re.compile(r"(?:^|/)\.env(?:\.[^/]+)?$"),
    re.compile(r"(?:^|/)credentials?(?:\.[^/]+)?$", re.IGNORECASE),
    re.compile(r"\.pem$"),
    re.compile(r"\.key$"),
    re.compile(r"id_rsa"),
)


class DisallowedPathError(ValueError):
    """Path rejeitado pelo allowlist — possível tentativa de injection."""


def _normalize(path: str) -> str:
    if not path:
        raise DisallowedPathError("file_path vazio")
    # Unificar separadores e remover leading slash
    normalized = path.replace("\\", "/").lstrip("/")
    if ".." in normalized.split("/"):
        raise DisallowedPathError(
            f"Path '{path}' contém '..' — path traversal não permitido"
        )
    return normalized


def is_path_allowed(path: str) -> bool:
    """True se o path pode ser modificado pelo agente."""
    try:
        validate_path(path)
    except DisallowedPathError:
        return False
    return True


def validate_path(path: str) -> str:
    """Valida um path; retorna a forma normalizada ou levanta.

    Raises:
        DisallowedPathError: path fora do allowlist ou em padrão negado.
    """
    normalized = _normalize(path)

    for pattern in DENIED_PATH_PATTERNS:
        if pattern.search(normalized):
            raise DisallowedPathError(
                f"Path '{path}' casa padrão bloqueado "
                f"({pattern.pattern}). Observer Agent não escreve em "
                f"caminhos sensíveis (.github, infra, deploy, secrets, "
                f"credenciais, chaves privadas)."
            )

    if not any(
        normalized.startswith(prefix) for prefix in ALLOWED_PATH_PREFIXES
    ):
        allowed = ", ".join(ALLOWED_PATH_PREFIXES)
        raise DisallowedPathError(
            f"Path '{path}' fora do allowlist. "
            f"Prefixos permitidos: {allowed}"
        )

    return normalized


def validate_fixes(fixes: list[dict]) -> list[dict]:
    """Valida uma lista de fixes; retorna a mesma lista com paths normalizados.

    Raises:
        DisallowedPathError: qualquer fix com path inválido aborta a
            operação. Não aplicamos parcialmente.
    """
    validated = []
    for fix in fixes:
        path = fix.get("file_path", "")
        normalized = validate_path(path)
        validated.append({**fix, "file_path": normalized})
    return validated
