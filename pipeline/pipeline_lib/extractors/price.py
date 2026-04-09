"""Extrator de valores monetários (R$)."""

import re

PATTERN = r"R\$\s?(\d{1,3}(?:\.\d{3})+(?:,\d{2})?|\d+(?:,\d{2})?|\d+)"


def extract(text: str | None) -> list[float]:
    """Extrai valores em R$ do texto, retorna como float."""
    if not text:
        return []
    matches = re.findall(PATTERN, text)
    values = []
    for m in matches:
        cleaned = m.replace(".", "").replace(",", ".")
        try:
            values.append(float(cleaned))
        except ValueError:
            continue
    return values
