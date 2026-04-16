"""Testes do pubsub backend (T4 Phase 3)."""

from __future__ import annotations

import asyncio

import pytest

from app.services.pubsub_backend import (
    InMemoryPubSub,
    _is_terminal_event,
    _redact_redis_url,
)


@pytest.mark.asyncio
async def test_inmemory_publish_then_subscribe_delivery():
    backend = InMemoryPubSub()
    q = backend.register("dep-1")
    await backend.publish(
        "dep-1", {"type": "log", "data": {"message": "hello"}}
    )
    event = q.get_nowait()
    assert event["data"]["message"] == "hello"


@pytest.mark.asyncio
async def test_inmemory_drop_oldest_on_terminal_event_queue_full():
    backend = InMemoryPubSub()
    q = backend.register("dep-1")
    # Enche a queue com evento nao-terminal
    for i in range(1000):
        q.put_nowait({"type": "log", "data": {"i": i}})
    assert q.full()

    # Publica terminal — deve dropar oldest e inserir terminal
    await backend.publish(
        "dep-1",
        {"type": "complete", "data": {"status": "success"}},
    )
    # Ultimo item deve ser o terminal
    items: list[dict] = []
    try:
        while True:
            items.append(q.get_nowait())
    except asyncio.QueueEmpty:
        pass
    assert items[-1]["type"] == "complete"


@pytest.mark.asyncio
async def test_inmemory_drop_nonterminal_event_queue_full():
    backend = InMemoryPubSub()
    q = backend.register("dep-1")
    for i in range(1000):
        q.put_nowait({"type": "log", "data": {"i": i}})

    await backend.publish(
        "dep-1", {"type": "log", "data": {"message": "dropped"}}
    )
    # Queue permanece com os originais
    items: list[dict] = []
    try:
        while True:
            items.append(q.get_nowait())
    except asyncio.QueueEmpty:
        pass
    assert items[0]["data"]["i"] == 0
    assert items[-1]["data"]["i"] == 999
    assert not any(e["data"].get("message") == "dropped" for e in items)


@pytest.mark.asyncio
async def test_inmemory_multiple_subscribers_all_receive():
    backend = InMemoryPubSub()
    q1 = backend.register("dep-1")
    q2 = backend.register("dep-1")

    await backend.publish("dep-1", {"type": "log"})
    assert q1.qsize() == 1
    assert q2.qsize() == 1


@pytest.mark.asyncio
async def test_inmemory_publish_to_deployment_without_subs_is_noop():
    backend = InMemoryPubSub()
    # Nao registra nada — publicar nao deve explodir
    await backend.publish("dep-ghost", {"type": "log"})


@pytest.mark.asyncio
async def test_inmemory_unsubscribe_removes_queue():
    backend = InMemoryPubSub()
    q = backend.register("dep-1")
    await backend.unsubscribe("dep-1", q)
    # Publish subsequente nao deve ir pra queue removida
    await backend.publish("dep-1", {"type": "log"})
    assert q.qsize() == 0


@pytest.mark.asyncio
async def test_inmemory_async_subscribe_iterator():
    backend = InMemoryPubSub()
    received: list[dict] = []

    async def consumer():
        async for event in backend.subscribe("dep-1"):
            received.append(event)
            if event.get("type") == "complete":
                break

    task = asyncio.create_task(consumer())
    # Yield pra consumer registrar queue
    await asyncio.sleep(0.01)
    await backend.publish("dep-1", {"type": "log"})
    await backend.publish("dep-1", {"type": "complete"})
    await asyncio.wait_for(task, timeout=1.0)

    assert len(received) == 2
    assert received[1]["type"] == "complete"


class TestTerminalEventDetection:
    def test_complete_is_terminal(self):
        assert _is_terminal_event({"type": "complete"})

    def test_error_is_terminal(self):
        assert _is_terminal_event({"type": "error"})

    def test_status_change_success_terminal(self):
        assert _is_terminal_event(
            {"type": "status_change", "data": {"status": "success"}}
        )

    def test_status_change_failed_terminal(self):
        assert _is_terminal_event(
            {"type": "status_change", "data": {"status": "failed"}}
        )

    def test_status_change_cancelled_terminal(self):
        assert _is_terminal_event(
            {"type": "status_change", "data": {"status": "cancelled"}}
        )

    def test_status_change_running_not_terminal(self):
        assert not _is_terminal_event(
            {"type": "status_change", "data": {"status": "running"}}
        )

    def test_log_not_terminal(self):
        assert not _is_terminal_event({"type": "log"})


class TestRedactRedisUrl:
    def test_no_credentials_preserved(self):
        assert (
            _redact_redis_url("redis://localhost:6379/0")
            == "redis://localhost:6379/0"
        )

    def test_password_redacted(self):
        assert (
            _redact_redis_url("redis://:supersecret@host:6379/0")
            == "redis://***@host:6379/0"
        )

    def test_user_password_redacted(self):
        assert (
            _redact_redis_url("redis://user:pw@host:6379/0")
            == "redis://***@host:6379/0"
        )
