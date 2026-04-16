"""Testes do LogEmitter (T4 Phase 5)."""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.log_emitter import LogEmitter


def _make_emitter(
    *,
    cancel_event: asyncio.Event | None = None,
    publish: AsyncMock | None = None,
) -> tuple[LogEmitter, AsyncMock, MagicMock, asyncio.Event]:
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    cancel_event = cancel_event or asyncio.Event()
    publish = publish or AsyncMock()
    emitter = LogEmitter(
        db=db,
        deployment_id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
        cancel_event=cancel_event,
        publish=publish,
        log_lock=asyncio.Lock(),
    )
    return emitter, publish, db, cancel_event


@pytest.mark.asyncio
async def test_emits_log_persists_and_publishes():
    emitter, publish, db, _ = _make_emitter()

    await emitter("info", "hello world", "s3")

    db.add.assert_called_once()
    db.flush.assert_awaited_once()
    publish.assert_awaited_once()
    args = publish.await_args.args
    dep_id_str, event = args
    assert dep_id_str == "33333333-3333-3333-3333-333333333333"
    assert event["type"] == "log"
    assert event["data"]["level"] == "info"
    assert event["data"]["message"] == "hello world"
    assert event["data"]["step_id"] == "s3"
    assert "timestamp" in event["data"]


@pytest.mark.asyncio
async def test_emits_log_without_step_id():
    emitter, publish, _, _ = _make_emitter()
    await emitter("warn", "standalone")
    event = publish.await_args.args[1]
    assert event["data"]["step_id"] is None


@pytest.mark.asyncio
async def test_skip_when_cancel_event_set():
    cancel = asyncio.Event()
    cancel.set()
    emitter, publish, db, _ = _make_emitter(cancel_event=cancel)

    await emitter("info", "should skip")

    db.add.assert_not_called()
    publish.assert_not_awaited()


@pytest.mark.asyncio
async def test_lock_serializes_concurrent_emits():
    emitter, publish, db, _ = _make_emitter()

    async def emit(level: str):
        await emitter(level, f"msg-{level}", "s3")

    # 10 emits concorrentes — nao deve explodir, lock sincroniza
    await asyncio.gather(*(emit(f"l{i}") for i in range(10)))

    assert db.add.call_count == 10
    assert publish.await_count == 10


@pytest.mark.asyncio
async def test_propagates_flush_exception():
    emitter, _, db, _ = _make_emitter()
    db.flush = AsyncMock(side_effect=RuntimeError("db boom"))

    with pytest.raises(RuntimeError, match="db boom"):
        await emitter("error", "msg")
