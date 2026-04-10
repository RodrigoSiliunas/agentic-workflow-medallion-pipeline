"""Extrator de placa de veículo (Mercosul e antiga)."""

import re

PATTERN_MERCOSUL = r"\b([A-Z]{3}\d[A-Z0-9]\d{2})\b"
PATTERN_OLD = r"\b([A-Z]{3}-?\d{4})\b"


def extract(text: str | None) -> list[str]:
    """Extrai placas do texto."""
    if not text:
        return []
    text_upper = text.upper()
    mercosul = re.findall(PATTERN_MERCOSUL, text_upper)
    old = re.findall(PATTERN_OLD, text_upper)
    return list(set(mercosul + old))


def mask(plate: str) -> str:
    """'SYL8V26' -> 'S**8*26'."""
    clean = re.sub(r"[^A-Za-z0-9]", "", plate).upper()
    if len(clean) == 7:
        return f"{clean[0]}**{clean[3]}*{clean[5:]}"
    return "***-****"
