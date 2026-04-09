"""Redação de PII no message_body (texto livre)."""

import re

from pipeline_lib.extractors.cpf import PATTERN as CPF_PATTERN
from pipeline_lib.extractors.email import PATTERN as EMAIL_PATTERN
from pipeline_lib.extractors.plate import PATTERN_MERCOSUL, PATTERN_OLD
from pipeline_lib.masking.format_preserving import mask_cpf, mask_email, mask_plate


def redact_message_body(text: str | None) -> str | None:
    """Substitui dados sensíveis no texto livre por versões mascaradas."""
    if text is None:
        return None
    if not text:
        return text

    # CPF primeiro (antes de telefone, para evitar conflito de dígitos)
    text = re.sub(CPF_PATTERN, lambda m: mask_cpf(m.group()), text)

    # Email
    text = re.sub(EMAIL_PATTERN, lambda m: mask_email(m.group()), text)

    # Placas (Mercosul e antiga)
    text = re.sub(PATTERN_MERCOSUL, lambda m: mask_plate(m.group()), text, flags=re.IGNORECASE)
    text = re.sub(PATTERN_OLD, lambda m: mask_plate(m.group()), text, flags=re.IGNORECASE)

    return text
