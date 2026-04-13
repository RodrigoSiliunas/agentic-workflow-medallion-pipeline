"""Omni Message Poller — processa mensagens dos canais externos.

Anti-spam:
- Usa Redis SET para persistir IDs de eventos ja processados (sobrevive reloads)
- Delay inicial de 5s para evitar corrida com uvicorn --reload
- Ignora grupos e mensagens sem texto
"""

import asyncio
from datetime import UTC, datetime

import redis.asyncio as aioredis
import structlog

from app.core.config import settings
from app.database.session import AsyncSessionLocal
from app.services.channel_handler import ChannelMessageHandler
from app.services.omni_service import OmniService

logger = structlog.get_logger()

POLL_INTERVAL = 3
REDIS_KEY = "omni:processed_events"
STARTUP_GRACE = 5  # segundos antes do primeiro poll


async def poll_loop() -> None:
    """Loop principal do poller."""
    omni = OmniService()

    # Aguardar Omni
    logger.info("Omni poller aguardando gateway...")
    for _ in range(30):
        if await omni.health_check():
            break
        await asyncio.sleep(2)
    else:
        logger.warning("Omni nao respondeu — poller desativado")
        return

    # Conectar Redis para dedup persistente
    try:
        redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await redis.ping()
        logger.info("Omni poller: Redis conectado para dedup")
    except Exception as exc:
        logger.warning("Redis indisponivel, usando dedup in-memory", error=str(exc))
        redis = None

    fallback_set: set[str] = set()

    # Grace period — evita processar durante cascata de reloads
    await asyncio.sleep(STARTUP_GRACE)

    startup_ts = datetime.now(UTC)
    logger.info("Omni poller iniciado", interval=POLL_INTERVAL)

    while True:
        try:
            events = await omni.get_new_events(limit=10)

            for event in events:
                eid = event.get("id", "")

                # Dedup via Redis ou fallback
                if redis:
                    already = await redis.sismember(REDIS_KEY, eid)
                    if already:
                        continue
                else:
                    if eid in fallback_set:
                        continue

                # Ignorar eventos pre-startup
                received_at = event.get("receivedAt", "")
                try:
                    ts = datetime.fromisoformat(received_at.replace("Z", "+00:00"))
                    if ts < startup_ts:
                        if redis:
                            await redis.sadd(REDIS_KEY, eid)
                        else:
                            fallback_set.add(eid)
                        continue
                except (ValueError, TypeError):
                    continue

                # Marcar como processado ANTES de processar (evita duplicata em caso de erro)
                if redis:
                    await redis.sadd(REDIS_KEY, eid)
                    # TTL de 24h para nao crescer infinitamente
                    await redis.expire(REDIS_KEY, 86400)
                else:
                    fallback_set.add(eid)

                # Processar
                try:
                    async with AsyncSessionLocal() as db:
                        handler = ChannelMessageHandler(db, omni)
                        await handler.handle_event(event)
                except Exception as exc:
                    logger.error("Erro ao processar evento", event_id=eid, error=str(exc))

        except asyncio.CancelledError:
            logger.info("Omni poller encerrado")
            if redis:
                await redis.aclose()
            return
        except Exception as exc:
            logger.error("Omni poller erro", error=str(exc))

        await asyncio.sleep(POLL_INTERVAL)
