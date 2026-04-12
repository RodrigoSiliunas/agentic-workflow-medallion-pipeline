"""Rate limiting Redis-backed com fallback in-memory.

Uso como FastAPI Dependency:

    @router.post("/login", dependencies=[Depends(rate_limit_auth)])
    async def login(...): ...
"""

import time
from collections import defaultdict

import structlog
from fastapi import Depends, HTTPException, Request, status

from app.core.config import settings

logger = structlog.get_logger()

# Fallback in-memory quando Redis indisponivel
_memory_store: dict[str, list[float]] = defaultdict(list)


class RateLimiter:
    """Sliding window rate limiter."""

    def __init__(self, redis_client=None):
        self.redis = redis_client

    async def check(
        self, key: str, limit: int, window_seconds: int = 60
    ) -> tuple[bool, int]:
        """Verifica rate limit. Retorna (allowed, remaining)."""
        if self.redis:
            return await self._check_redis(key, limit, window_seconds)
        return self._check_memory(key, limit, window_seconds)

    async def _check_redis(
        self, key: str, limit: int, window: int
    ) -> tuple[bool, int]:
        try:
            now = time.time()
            pipe = self.redis.pipeline()
            pipe.zremrangebyscore(key, 0, now - window)
            pipe.zadd(key, {str(now): now})
            pipe.zcard(key)
            pipe.expire(key, window)
            results = await pipe.execute()
            count = results[2]
            remaining = max(0, limit - count)
            return count <= limit, remaining
        except Exception as e:
            logger.warning("Redis rate limit fallback", error=str(e))
            return self._check_memory(key, limit, window)

    def _check_memory(
        self, key: str, limit: int, window: int
    ) -> tuple[bool, int]:
        now = time.time()
        cutoff = now - window
        _memory_store[key] = [t for t in _memory_store[key] if t > cutoff]
        _memory_store[key].append(now)
        count = len(_memory_store[key])
        remaining = max(0, limit - count)
        return count <= limit, remaining


# Channel-specific limits
CHANNEL_LIMITS = {
    "whatsapp": {"limit": 1500, "window": 86400},  # 1500/dia
    "discord": {"limit": 50, "window": 1},  # 50/s
    "telegram": {"limit": 30, "window": 1},  # 30/s
    "web": {"limit": 60, "window": 60},  # 60/min
}

# Singleton — sem Redis por enquanto (fallback in-memory).
_limiter = RateLimiter()


def _client_ip(request: Request) -> str:
    """Extrai IP do client pra usar como chave do rate limiter."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _rate_limit(limit: int, window: int = 60, prefix: str = "rl"):
    """Factory de dependency que aplica rate limiting por IP."""

    async def _check(request: Request) -> None:
        ip = _client_ip(request)
        key = f"{prefix}:{ip}"
        allowed, remaining = await _limiter.check(key, limit, window)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit excedido ({limit} reqs/{window}s). Tente novamente em breve.",
                headers={"Retry-After": str(window)},
            )

    return Depends(_check)


# Dependencies prontas pra usar em rotas
rate_limit_auth = _rate_limit(
    limit=settings.RATE_LIMIT_AUTH_PER_MINUTE,
    window=60,
    prefix="rl:auth",
)

rate_limit_api = _rate_limit(
    limit=settings.RATE_LIMIT_PER_MINUTE,
    window=60,
    prefix="rl:api",
)

rate_limit_webhook = _rate_limit(
    limit=30,
    window=60,
    prefix="rl:webhook",
)
