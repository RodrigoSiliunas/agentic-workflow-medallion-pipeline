"""Extrator de seguradoras concorrentes."""

import re

COMPETITORS: dict[str, str] = {
    r"porto\s*seguro": "porto seguro",
    r"azul\s*seguros?": "azul",
    r"bradesco\s*seguros?": "bradesco",
    r"sulam[eé]rica": "sulamerica",
    r"liberty": "liberty",
    r"allianz": "allianz",
    r"hdi\s*seguros?": "hdi",
    r"mapfre": "mapfre",
    r"tokio\s*marine": "tokio marine",
    r"zurich": "zurich",
}


def extract(text: str | None) -> list[str]:
    """Extrai seguradoras concorrentes mencionadas no texto."""
    if not text:
        return []
    text_lower = text.lower()
    found = []
    for pattern, name in COMPETITORS.items():
        if re.search(pattern, text_lower):
            found.append(name)
    return found
