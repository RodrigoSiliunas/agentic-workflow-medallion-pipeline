"""Tests para _is_cancelled — branch local + branch Redis cross-worker."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.services.deployment_saga import _is_cancelled, _redis_async


@pytest.mark.asyncio
async def test_local_event_set_returns_true():
    """Quando o asyncio.Event do worker atual ta set, retorna True sem
    consultar Redis (short-circuit)."""
    event = asyncio.Event()
    event.set()
    assert await _is_cancelled("dep-1", event) is True


@pytest.mark.asyncio
async def test_local_event_unset_no_redis_returns_false():
    """Sem Redis disponivel + event local nao set → False."""
    event = asyncio.Event()
    with patch(
        "app.services.deployment_saga._redis_async", new=AsyncMock(return_value=None)
    ):
        assert await _is_cancelled("dep-2", event) is False


@pytest.mark.asyncio
async def test_redis_flag_set_returns_true_cross_worker():
    """Outro worker setou flag em Redis — _is_cancelled retorna True
    mesmo com event local nao set (cross-worker cancellation)."""
    event = asyncio.Event()
    fake_client = AsyncMock()
    fake_client.exists = AsyncMock(return_value=1)
    fake_client.aclose = AsyncMock()

    with patch(
        "app.services.deployment_saga._redis_async",
        new=AsyncMock(return_value=fake_client),
    ):
        result = await _is_cancelled("dep-3", event)

    assert result is True
    fake_client.exists.assert_awaited_once_with("saga:cancel:dep-3")
    fake_client.aclose.assert_awaited()


@pytest.mark.asyncio
async def test_redis_flag_absent_returns_false():
    """Redis disponivel mas key nao existe → False."""
    event = asyncio.Event()
    fake_client = AsyncMock()
    fake_client.exists = AsyncMock(return_value=0)
    fake_client.aclose = AsyncMock()

    with patch(
        "app.services.deployment_saga._redis_async",
        new=AsyncMock(return_value=fake_client),
    ):
        result = await _is_cancelled("dep-4", event)

    assert result is False
    fake_client.exists.assert_awaited_once()


@pytest.mark.asyncio
async def test_redis_exception_returns_false_no_raise():
    """Falha do Redis nao quebra saga — retorna False (assume not cancelled)."""
    event = asyncio.Event()
    fake_client = AsyncMock()
    fake_client.exists = AsyncMock(side_effect=ConnectionError("redis down"))
    fake_client.aclose = AsyncMock()

    with patch(
        "app.services.deployment_saga._redis_async",
        new=AsyncMock(return_value=fake_client),
    ):
        result = await _is_cancelled("dep-5", event)

    assert result is False
    # aclose ainda chamado em finally
    fake_client.aclose.assert_awaited()


@pytest.mark.asyncio
async def test_redis_async_returns_none_when_no_url():
    """REDIS_URL vazio → _redis_async retorna None."""
    with patch("app.services.deployment_saga.settings") as mock_settings:
        mock_settings.REDIS_URL = ""
        client = await _redis_async()
        assert client is None
