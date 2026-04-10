"""Extrator de telefone brasileiro."""

import re

PATTERN = r"(?:\+?55\s?)?(?:\(?\d{2}\)?\s?)(?:9\s?)?\d{4}[\s-]?\d{4}"


def extract(text: str | None) -> list[str]:
    """Extrai telefones do texto."""
    if not text:
        return []
    return re.findall(PATTERN, text)


def mask(phone: str) -> str:
    """'(11) 98765-4321' -> '(11) ****-4321'."""
    digits = re.sub(r"\D", "", phone)
    if len(digits) >= 10:
        return f"({digits[:2]}) ****-{digits[-4:]}"
    return "(**) ****-****"
