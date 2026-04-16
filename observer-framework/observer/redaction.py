"""Redação de PII em strings que saem do Observer.

Aplicado a qualquer dado enviado ao LLM externo (Anthropic, OpenAI) ou
escrito em PR body do GitHub. Evita vazar PII brasileira (CPF, CNPJ,
telefone, email) para terceiros.

Regras:
- Zero dependência de `pipeline_lib` — preserva a independência entre
  observer-framework e os pipelines.
- Não reversível. Substitui por marcador `<REDACTED:TYPE>`.
- Ordem importa: redigir CNPJ antes de CPF evita que CPF regex
  consuma parte de um CNPJ.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = [
    "PIIRedactor",
    "RedactionRule",
    "redact",
]


@dataclass(frozen=True)
class RedactionRule:
    """Regra de redação: regex + rótulo."""

    name: str
    pattern: re.Pattern[str]

    def apply(self, text: str) -> tuple[str, int]:
        """Retorna (texto_redigido, qtd_ocorrencias)."""
        redacted, count = self.pattern.subn(f"<REDACTED:{self.name}>", text)
        return redacted, count


# Ordem crítica: CNPJ > CPF > telefone > token > email.
DEFAULT_RULES: tuple[RedactionRule, ...] = (
    RedactionRule(
        name="CNPJ",
        pattern=re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b"),
    ),
    RedactionRule(
        name="CPF",
        pattern=re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"),
    ),
    RedactionRule(
        name="PHONE_BR",
        # +55 (11) 98765-4321, (11) 9876-5432, 11987654321
        pattern=re.compile(
            r"(?:\+?55[\s-]?)?"
            r"(?:\(?\d{2}\)?[\s-]?)"
            r"9?\d{4}[\s-]?\d{4}\b"
        ),
    ),
    RedactionRule(
        name="EMAIL",
        pattern=re.compile(
            r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"
        ),
    ),
    RedactionRule(
        name="BEARER_TOKEN",
        pattern=re.compile(r"\bBearer\s+[A-Za-z0-9\-_\.=]+", re.IGNORECASE),
    ),
    RedactionRule(
        name="AWS_KEY",
        pattern=re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    ),
    RedactionRule(
        name="GITHUB_PAT",
        pattern=re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    ),
    RedactionRule(
        name="ANTHROPIC_KEY",
        pattern=re.compile(r"\bsk-ant-[A-Za-z0-9\-_]{20,}\b"),
    ),
)


class PIIRedactor:
    """Aplica um conjunto de RedactionRule a strings arbitrárias."""

    def __init__(
        self, rules: tuple[RedactionRule, ...] = DEFAULT_RULES
    ) -> None:
        self._rules = rules

    def redact(self, text: str | None) -> str:
        if not text:
            return text or ""
        result = text
        for rule in self._rules:
            result, _ = rule.apply(result)
        return result

    def redact_dict(self, data: dict) -> dict:
        """Aplica redação recursiva em valores string de um dict.

        Chaves são preservadas. Listas e dicts aninhados são percorridos.
        """
        return {k: self._redact_value(v) for k, v in data.items()}

    def _redact_value(self, value):
        if isinstance(value, str):
            return self.redact(value)
        if isinstance(value, dict):
            return self.redact_dict(value)
        if isinstance(value, list):
            return [self._redact_value(v) for v in value]
        return value


_DEFAULT = PIIRedactor()


def redact(text: str | None) -> str:
    """Atalho: redige PII usando as regras default."""
    return _DEFAULT.redact(text)
