"""Extrator e validador de CPF."""

import re

PATTERN = r"\b(\d{3}\.?\d{3}\.?\d{3}-?\d{2})\b"


def extract(text: str | None) -> list[str]:
    """Extrai CPFs do texto."""
    if not text:
        return []
    return re.findall(PATTERN, text)


def validate(cpf: str) -> bool:
    """Valida CPF pelos dígitos verificadores."""
    digits = re.sub(r"\D", "", cpf)
    if len(digits) != 11 or len(set(digits)) == 1:
        return False

    for i in range(9, 11):
        total = sum(int(digits[j]) * ((i + 1) - j) for j in range(i))
        digit = (total * 10 % 11) % 10
        if digit != int(digits[i]):
            return False
    return True


def mask(cpf: str) -> str:
    """'383.182.856-05' -> '***.***.856-05'."""
    digits = re.sub(r"\D", "", cpf)
    if len(digits) != 11:
        return "***.***.***-**"
    return f"***.***.{digits[6:9]}-{digits[9:]}"
