"""Pub/Sub backend para eventos SSE do deployment saga (T4 Phase 3).

Dois backends plugaveis:
- `InMemoryPubSub` — default. asyncio.Queue por subscriber. Funciona em
  single-worker uvicorn. Usado automaticamente se Redis nao disponivel.
- `RedisPubSub` — produção. Channel `deploy:{deployment_id}` em Redis.
  Habilita escala horizontal (múltiplos workers recebem eventos).

`get_pubsub()` escolhe o backend na primeira chamada com base em
`settings.REDIS_URL` + health check. Fallback transparente pra
in-memory se Redis unreachable.

Contract:
    async def publish(deployment_id: str, event: dict) -> None
    async def subscribe(deployment_id: str) -> AsyncIterator[dict]
    async def close() -> None
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections import defaultdict
from collections.abc import AsyncIterator
from typing import Any, Protocol

import structlog

from app.core.config import settings

logger = structlog.get_logger()

# TTL dos eventos replay-able em Redis (list tail por deployment).
# Nao queremos guardar historico longo — SSE e eventos transitorios.
REDIS_EVENT_TTL_SECONDS = 3600


class PubSubBackend(Protocol):
    async def publish(self, deployment_id: str, event: dict[str, Any]) -> None: ...

    def subscribe(self, deployment_id: str) -> AsyncIterator[dict[str, Any]]: ...

    async def unsubscribe(
        self, deployment_id: str, queue: asyncio.Queue[dict[str, Any]]
    ) -> None: ...

    async def close(self) -> None: ...


class InMemoryPubSub:
    """Backend in-process. Fanout via asyncio.Queue por subscriber."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue[dict[str, Any]]]] = defaultdict(list)

    def _new_queue(self) -> asyncio.Queue[dict[str, Any]]:
        return asyncio.Queue(maxsize=1000)

    def register(self, deployment_id: str) -> asyncio.Queue[dict[str, Any]]:
        """API alternativa compat — retorna a queue pra consumidor manual."""
        queue = self._new_queue()
        self._subscribers[deployment_id].append(queue)
        return queue

    async def publish(self, deployment_id: str, event: dict[str, Any]) -> None:
        is_terminal = _is_terminal_event(event)
        for queue in list(self._subscribers.get(deployment_id, [])):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                if is_terminal:
                    try:
                        queue.get_nowait()
                        queue.put_nowait(event)
                    except (asyncio.QueueEmpty, asyncio.QueueFull):
                        logger.warning(
                            "sse queue full, could not deliver terminal event",
                            deployment_id=deployment_id,
                        )
                else:
                    logger.warning(
                        "sse queue full, dropping non-terminal event",
                        deployment_id=deployment_id,
                    )

    async def unsubscribe(
        self, deployment_id: str, queue: asyncio.Queue[dict[str, Any]]
    ) -> None:
        subs = self._subscribers.get(deployment_id, [])
        if queue in subs:
            subs.remove(queue)
        if not subs:
            self._subscribers.pop(deployment_id, None)

    async def subscribe(
        self, deployment_id: str
    ) -> AsyncIterator[dict[str, Any]]:
        queue = self.register(deployment_id)
        try:
            while True:
                event = await queue.get()
                yield event
        finally:
            await self.unsubscribe(deployment_id, queue)

    async def close(self) -> None:
        self._subscribers.clear()


class RedisPubSub:
    """Backend Redis. Channel `deploy:{deployment_id}`.

    Cada worker (uvicorn process) roda seu proprio subscribe quando o
    cliente SSE conecta. `publish` vira PUBLISH no channel; todos os
    workers (incluindo o que publicou) recebem e fanout pro queue
    local do cliente conectado naquele worker.
    """

    def __init__(self, redis_url: str) -> None:
        # Import tardio — dep opcional
        import redis.asyncio as redis

        self._redis = redis.from_url(redis_url, decode_responses=True)

    @staticmethod
    def _channel(deployment_id: str) -> str:
        return f"deploy:{deployment_id}"

    async def publish(self, deployment_id: str, event: dict[str, Any]) -> None:
        payload = json.dumps(event, default=str)
        await self._redis.publish(self._channel(deployment_id), payload)

    async def subscribe(
        self, deployment_id: str
    ) -> AsyncIterator[dict[str, Any]]:
        pubsub = self._redis.pubsub()
        try:
            await pubsub.subscribe(self._channel(deployment_id))
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                raw = message.get("data")
                if raw is None:
                    continue
                try:
                    yield json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    logger.warning(
                        "redis pubsub: dropping malformed event",
                        deployment_id=deployment_id,
                    )
        finally:
            with contextlib.suppress(Exception):
                await pubsub.unsubscribe(self._channel(deployment_id))
                await pubsub.close()

    async def unsubscribe(
        self, deployment_id: str, queue: asyncio.Queue[dict[str, Any]]
    ) -> None:
        # Redis backend cleans up via subscribe() generator's finally.
        # Metodo mantido para compat com Protocol.
        return None

    async def close(self) -> None:
        with contextlib.suppress(Exception):
            await self._redis.aclose()


def _is_terminal_event(event: dict[str, Any]) -> bool:
    if event.get("type") in ("complete", "error"):
        return True
    if event.get("type") == "status_change":
        status = (event.get("data") or {}).get("status")
        return status in ("success", "failed", "cancelled")
    return False


_BACKEND: PubSubBackend | None = None
_BACKEND_LOCK = asyncio.Lock()


async def get_pubsub() -> PubSubBackend:
    """Devolve backend ativo. Escolhe Redis se disponivel, senao in-memory.

    Primeira chamada faz health-check; resultado e cached.
    """
    global _BACKEND
    if _BACKEND is not None:
        return _BACKEND
    async with _BACKEND_LOCK:
        if _BACKEND is not None:
            return _BACKEND
        _BACKEND = await _build_backend()
        return _BACKEND


async def _build_backend() -> PubSubBackend:
    redis_url = getattr(settings, "REDIS_URL", "") or ""
    if not redis_url:
        logger.info("pubsub backend: in-memory (REDIS_URL vazio)")
        return InMemoryPubSub()

    try:
        backend = RedisPubSub(redis_url)
        # Health check rapido
        await backend._redis.ping()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "pubsub backend: redis unreachable, caindo pra in-memory",
            error=str(exc),
        )
        return InMemoryPubSub()

    logger.info("pubsub backend: redis", url=_redact_redis_url(redis_url))
    return backend


def _redact_redis_url(url: str) -> str:
    """Remove credenciais do URL pra log seguro."""
    if "@" not in url:
        return url
    scheme, rest = url.split("://", 1)
    _, host = rest.split("@", 1)
    return f"{scheme}://***@{host}"


async def reset_pubsub_for_tests() -> None:
    """Reset do singleton — usado em testes."""
    global _BACKEND
    if _BACKEND is not None:
        await _BACKEND.close()
    _BACKEND = None
