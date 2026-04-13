"""Omni Message Poller — processa mensagens recebidas via WhatsApp/Discord/Telegram.

Roda como background task no lifespan do FastAPI. Consulta eventos novos
no Omni a cada N segundos e responde via LLM ou mensagem padrao.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import structlog

from app.services.omni_service import OmniService

logger = structlog.get_logger()

# IDs de eventos ja processados (em memoria — nao persiste entre restarts)
_processed_events: set[str] = set()

POLL_INTERVAL = 5  # segundos entre polls
MAX_EVENT_AGE = timedelta(minutes=2)  # ignorar mensagens mais velhas que 2 min
GREETING = (
    "Ola! Sou o assistente virtual da Safatechx. "
    "Posso ajudar com informacoes sobre seus pipelines de dados. "
    "O que voce precisa?"
)


def _is_group_chat(event: dict) -> bool:
    """Verifica se o evento e de grupo (ignorar)."""
    chat_id = event.get("chatId", "")
    raw = event.get("rawPayload", {})
    key = raw.get("key", {})
    jid = key.get("remoteJid", chat_id)
    return "@g.us" in jid or "@g.us" in chat_id


def _is_recent(event: dict) -> bool:
    """Verifica se o evento e recente o suficiente para processar."""
    received_at = event.get("receivedAt")
    if not received_at:
        return False
    try:
        ts = datetime.fromisoformat(received_at.replace("Z", "+00:00"))
        return datetime.now(UTC) - ts < MAX_EVENT_AGE
    except (ValueError, TypeError):
        return False


async def _handle_event(omni: OmniService, event: dict) -> None:
    """Processa um evento de mensagem recebida."""
    event_id = event["id"]
    text = event.get("textContent") or ""
    instance_id = event.get("instanceId", "")
    chat_id = event.get("chatId", "")

    # Ignorar mensagens de grupo
    if _is_group_chat(event):
        logger.debug("Mensagem de grupo ignorada", chat_id=chat_id)
        return

    # Ignorar mensagens antigas
    if not _is_recent(event):
        logger.debug("Mensagem antiga ignorada", event_id=event_id)
        return

    # Extrair JID do remetente (para enviar resposta)
    raw = event.get("rawPayload", {})
    key = raw.get("key", {})
    sender_jid = key.get("remoteJidAlt") or key.get("remoteJid") or chat_id

    if not text.strip() or not sender_jid:
        return

    sender_name = raw.get("pushName", "usuario")
    logger.info(
        "Mensagem recebida via Omni",
        sender=sender_name, text=text[:80], instance_id=instance_id,
    )

    # Resposta simples (greeting) — futuro: integrar com LLMOrchestrator
    reply = GREETING

    try:
        await omni.send_message(instance_id, sender_jid, reply)
        logger.info("Resposta enviada via Omni", sender=sender_name)
    except Exception as exc:
        logger.error("Falha ao enviar resposta via Omni", error=str(exc))


async def poll_loop() -> None:
    """Loop principal do poller — roda indefinidamente."""
    omni = OmniService()

    # Aguardar Omni ficar healthy antes de iniciar
    logger.info("Omni poller aguardando gateway...")
    for _ in range(30):
        if await omni.health_check():
            break
        await asyncio.sleep(2)
    else:
        logger.warning("Omni nao respondeu apos 60s — poller desativado")
        return

    logger.info("Omni poller iniciado", interval=POLL_INTERVAL)

    while True:
        try:
            events = await omni.get_new_events(limit=10)
            for event in events:
                eid = event.get("id", "")
                if eid in _processed_events:
                    continue
                _processed_events.add(eid)
                await _handle_event(omni, event)

            # Limitar memoria — manter apenas ultimos 500 IDs
            if len(_processed_events) > 500:
                excess = len(_processed_events) - 500
                for _ in range(excess):
                    _processed_events.pop()

        except asyncio.CancelledError:
            logger.info("Omni poller encerrado")
            return
        except Exception as exc:
            logger.error("Omni poller erro", error=str(exc))

        await asyncio.sleep(POLL_INTERVAL)
