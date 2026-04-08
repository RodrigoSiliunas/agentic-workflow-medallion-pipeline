"""Extrator de email."""

import re

PATTERN = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"


def extract(text: str | None) -> list[str]:
    """Extrai emails do texto."""
    if not text:
        return []
    return re.findall(PATTERN, text)


def mask(email: str) -> str:
    """'joao.silva@gmail.com' -> 'j********a@gmail.com'."""
    user, domain = email.split("@")
    masked_user = "*" * len(user) if len(user) <= 2 else user[0] + "*" * (len(user) - 2) + user[-1]
    return f"{masked_user}@{domain}"
