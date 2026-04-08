"""Extrator de CEP."""

import re

PATTERN = r"\b(\d{5}-?\d{3})\b"


def extract(text: str | None) -> list[str]:
    """Extrai CEPs do texto."""
    if not text:
        return []
    return re.findall(PATTERN, text)
