"""Seguranca: JWT, bcrypt, Fernet encryption, token revocation."""

import uuid as _uuid
from datetime import UTC, datetime, timedelta

import redis
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


# Redis para token revocation (blacklist)
_revocation_redis: redis.Redis | None = None
_REVOKE_PREFIX = "jwt:revoked:"

try:
    _revocation_redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
    _revocation_redis.ping()
except Exception:
    _revocation_redis = None


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access", "jti": str(_uuid.uuid4())})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh", "jti": str(_uuid.uuid4())})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        # Verificar revocation
        jti = payload.get("jti")
        if jti and _revocation_redis and _revocation_redis.exists(f"{_REVOKE_PREFIX}{jti}"):
            return None
        return payload
    except JWTError:
        return None


def revoke_token(token: str) -> None:
    """Adiciona token na blacklist do Redis (TTL = tempo restante do token)."""
    payload = None
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM], options={"verify_exp": False},
        )
    except JWTError:
        return
    if not payload:
        return
    jti = payload.get("jti")
    exp = payload.get("exp")
    if not jti or not _revocation_redis:
        return
    # TTL = tempo restante ate expirar
    ttl = max(int(exp - datetime.now(UTC).timestamp()), 1) if exp else 900
    _revocation_redis.setex(f"{_REVOKE_PREFIX}{jti}", ttl, "1")


def encrypt_value(value: str) -> str:
    """Criptografa valor com Fernet (para credenciais de empresa)."""
    return fernet.encrypt(value.encode()).decode()


def decrypt_value(encrypted: str) -> str:
    """Descriptografa valor com Fernet."""
    return fernet.decrypt(encrypted.encode()).decode()
