"""Mascaramento preservando formato e dimensões."""

import re


def mask_cpf(cpf: str) -> str:
    """'383.182.856-05' -> '***.***.856-05'."""
    digits = re.sub(r"\D", "", cpf)
    if len(digits) != 11:
        return "***.***.***-**"
    return f"***.***.{digits[6:9]}-{digits[9:]}"


def mask_email(email: str) -> str:
    """'joao.silva@gmail.com' -> 'j********a@gmail.com'."""
    parts = email.split("@")
    if len(parts) != 2:
        return "***@***.***"
    user, domain = parts
    masked_user = "*" * len(user) if len(user) <= 2 else user[0] + "*" * (len(user) - 2) + user[-1]
    return f"{masked_user}@{domain}"


def mask_phone(phone: str) -> str:
    """'(11) 98765-4321' -> '(11) ****-4321'."""
    digits = re.sub(r"\D", "", phone)
    if len(digits) >= 10:
        return f"({digits[:2]}) ****-{digits[-4:]}"
    return "(**) ****-****"


def mask_plate(plate: str) -> str:
    """'SYL8V26' -> 'S**8*26'."""
    clean = re.sub(r"[^A-Za-z0-9]", "", plate).upper()
    if len(clean) == 7:
        return f"{clean[0]}**{clean[3]}*{clean[5:]}"
    return "***-****"
