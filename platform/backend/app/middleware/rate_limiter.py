"""Rate limiting Redis-backed com fallback in-memory."""

import time
from collections import defaultdict

import structlog

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
