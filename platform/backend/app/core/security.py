"""Seguranca: JWT, bcrypt, Fernet encryption."""

from datetime import UTC, datetime, timedelta

from cryptography.fernet import Fernet
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Fernet encryption (SEPARADA do JWT — para credenciais de empresa).
# Fail-fast: se a key for o default sentinel, credenciais encriptadas
# ficariam irrecuperaveis no proximo restart (Fernet.generate_key() gera
# key aleatoria que morre com o processo).
if settings.ENCRYPTION_KEY == "change-me-encryption-key":
    raise RuntimeError(
        "ENCRYPTION_KEY nao configurada. Gere uma com:\n"
        '  python -c "from cryptography.fernet import Fernet;'
        ' print(Fernet.generate_key().decode())"\n'
        "e salve no .env do backend."
    )
_fernet_key = settings.ENCRYPTION_KEY.encode()
fernet = Fernet(_fernet_key)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None


def encrypt_value(value: str) -> str:
    """Criptografa valor com Fernet (para credenciais de empresa)."""
    return fernet.encrypt(value.encode()).decode()


def decrypt_value(encrypted: str) -> str:
    """Descriptografa valor com Fernet."""
    return fernet.decrypt(encrypted.encode()).decode()
