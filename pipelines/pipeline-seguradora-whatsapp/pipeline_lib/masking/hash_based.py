"""Mascaramento baseado em HMAC-SHA256 para joins determinísticos."""

import hashlib
import hmac
import os
import re


def hash_value(value: str) -> str:
    """Hash HMAC-SHA256 de um valor. Determinístico com mesma chave."""
    secret = os.environ["MASKING_SECRET"]  # OBRIGATÓRIO — KeyError se não configurado
    normalized = re.sub(r"\D", "", value)
    return hmac.new(secret.encode(), normalized.encode(), hashlib.sha256).hexdigest()[:16]
