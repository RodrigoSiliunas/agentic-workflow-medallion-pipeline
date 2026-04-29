"""Unit tests para ChannelMessageHandler — filtros + roteamento sem pipeline."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.channel_handler import ChannelMessageHandler


def _make_handler(
    *,
    startup_ts: datetime | None = None,
) -> tuple[ChannelMessageHandler, MagicMock, AsyncMock]:
    db = MagicMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    db.add = MagicMock()
    omni = AsyncMock()
    handler = ChannelMessageHandler(db=db, omni=omni, startup_ts=startup_ts)
    return handler, db, omni


def _event(
    *,
    text: str = "ola",
    sender_jid: str = "5511999999999@s.whatsapp.net",
    chat_id: str | None = None,
    is_from_me: bool = False,
    participant: str | None = None,
    msg_ts: int | None = None,
) -> dict:
    return {
        "textContent": text,
        "instanceId": "inst-1",
        "chatId": chat_id or sender_jid,
        "channel": "whatsapp",
        "rawPayload": {
            "key": {
                "remoteJid": sender_jid,
                "fromMe": is_from_me,
                "participant": participant,
            },
            "pushName": "Tester",
            "messageTimestamp": msg_ts,
        },
    }


@pytest.mark.asyncio
async def test_filters_messages_before_startup_ts():
    """msg com timestamp anterior ao startup_ts e ignorada (replay backlog)."""
    startup = datetime.now(UTC)
    handler, db, omni = _make_handler(startup_ts=startup)

    pre_ts = int((startup - timedelta(hours=1)).timestamp())
    await handler.handle_event(_event(msg_ts=pre_ts))

    db.execute.assert_not_called()
    omni.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_processes_messages_after_startup_ts():
    """msg com timestamp posterior segue fluxo (chega ao identity lookup)."""
    startup = datetime.now(UTC) - timedelta(hours=1)
    handler, db, omni = _make_handler(startup_ts=startup)

    # Mock identity lookup retorna None (onboarding flow)
    result = MagicMock()
    result.first = MagicMock(return_value=None)
    db.execute.return_value = result

    post_ts = int(datetime.now(UTC).timestamp())
    await handler.handle_event(_event(text="qualquer texto", msg_ts=post_ts))

    # Identity lookup foi chamado (1 query)
    assert db.execute.await_count >= 1
    omni.send_message.assert_awaited()


@pytest.mark.asyncio
async def test_ignores_groups_via_g_us_suffix():
    """JID @g.us = grupo, ignora."""
    handler, db, _ = _make_handler()

    await handler.handle_event(
        _event(sender_jid="123-456@g.us", chat_id="123-456@g.us")
    )

    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_ignores_groups_via_participant_field():
    """participant != None = msg de grupo (mesmo se JID nao terminar em @g.us)."""
    handler, db, _ = _make_handler()

    await handler.handle_event(
        _event(participant="111@s.whatsapp.net")
    )

    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_ignores_messages_from_self():
    """fromMe=True = bot ja respondeu, pular."""
    handler, db, _ = _make_handler()
    await handler.handle_event(_event(is_from_me=True))
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_ignores_empty_text():
    """text="" = nada pra processar."""
    handler, db, _ = _make_handler()
    await handler.handle_event(_event(text=""))
    db.execute.assert_not_called()
