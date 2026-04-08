"""Servico de criptografia Fernet para credenciais de empresa."""

from app.core.security import decrypt_value, encrypt_value


class EncryptionService:
    """Wrapper para operacoes de criptografia."""

    @staticmethod
    def encrypt(value: str) -> str:
        return encrypt_value(value)

    @staticmethod
    def decrypt(encrypted: str) -> str:
        return decrypt_value(encrypted)
