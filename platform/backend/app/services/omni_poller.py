"""Omni Message Poller — processa mensagens dos canais externos (WhatsApp/Discord/Telegram).

Roda como background task no lifespan do FastAPI. Consulta eventos novos
no Omni a cada N segundos e despacha para o ChannelMessageHandler.

Anti-spam: so processa eventos recebidos APOS o startup do poller.
"""

import asyncio
from datetime import UTC, datetime

import structlog

from app.database.session import AsyncSessionLocal
from app.services.channel_handler import ChannelMessageHandler
from app.services.omni_service import OmniService

logger = structlog.get_logger()

POLL_INTERVAL = 3  # segundos entre polls
_processed_events: set[str] = set()


async def poll_loop() -> None:
    """Loop principal do poller — roda indefinidamente."""
    omni = OmniService()

    # Aguardar Omni ficar healthy
    logger.info("Omni poller aguardando gateway...")
    for _ in range(30):
        if await omni.health_check():
            break
        await asyncio.sleep(2)
    else:
        logger.warning("Omni nao respondeu apos 60s — poller desativado")
        return

    # Timestamp de startup — ignorar eventos anteriores
    startup_ts = datetime.now(UTC)
    logger.info("Omni poller iniciado", interval=POLL_INTERVAL, since=startup_ts.isoformat())

    while True:
        try:
            events = await omni.get_new_events(limit=10)

            for event in events:
                eid = event.get("id", "")
                if eid in _processed_events:
                    continue

                # Ignorar eventos anteriores ao startup
                received_at = event.get("receivedAt", "")
                try:
                    ts = datetime.fromisoformat(received_at.replace("Z", "+00:00"))
                    if ts < startup_ts:
                        _processed_events.add(eid)
                        continue
                except (ValueError, TypeError):
                    _processed_events.add(eid)
                    continue

                _processed_events.add(eid)

                # Processar em sessao DB separada
                try:
                    async with AsyncSessionLocal() as db:
                        handler = ChannelMessageHandler(db, omni)
                        await handler.handle_event(event)
                except Exception as exc:
                    logger.error("Erro ao processar evento", event_id=eid, error=str(exc))

            # Limitar memoria
            if len(_processed_events) > 1000:
                to_remove = list(_processed_events)[:500]
                for item in to_remove:
                    _processed_events.discard(item)

        except asyncio.CancelledError:
            logger.info("Omni poller encerrado")
            return
        except Exception as exc:
            logger.error("Omni poller erro", error=str(exc))

        await asyncio.sleep(POLL_INTERVAL)
