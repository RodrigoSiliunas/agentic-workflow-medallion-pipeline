"""Mascaramento baseado em HMAC-SHA256 para joins deterministicos."""

import hashlib
import hmac
import os
import re


def hash_value(value: str) -> str:
    """Hash HMAC-SHA256 de um valor. Deterministico com mesma chave."""
    secret = os.environ["MASKING_SECRET"]  # OBRIGATORIO — KeyError se nao configurado
    normalized = re.sub(r"\D", "", value)
    return hmac.new(secret.encode(), normalized.encode(), hashlib.sha256).hexdigest()[:16]
