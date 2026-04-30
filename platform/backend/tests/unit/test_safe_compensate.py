"""Tests para SagaStepBase._safe_compensate.

Cobre:
- Sucesso async (sync=False)
- Sucesso sync (sync=True, roda em to_thread)
- Falha capturada (warn ao inves de raise)
- Compensate nao bloqueia rollback subsequent
"""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.services.real_saga.base import (
    DeploymentCredentials,
    SagaStepBase,
    SharedSagaState,
    StepContext,
)


def _make_ctx() -> tuple[StepContext, AsyncMock]:
    """Constroi StepContext minimo + retorna emit_log mockado."""
    deployment = type(
        "FakeDeployment",
        (),
        {"id": uuid.uuid4(), "company_id": uuid.uuid4(), "config": {}},
    )()
    emit = AsyncMock()
    ctx = StepContext(
        deployment=deployment,  # type: ignore[arg-type]
        step_id="testing",
        step_name="Testing",
        credentials=DeploymentCredentials(),
        emit_log=emit,
        state_dir=Path("/tmp"),
        shared=SharedSagaState(),
    )
    return ctx, emit


@pytest.mark.asyncio
async def test_safe_compensate_async_success_logs_ok():
    ctx, emit = _make_ctx()
    called = []

    async def _action():
        called.append("ran")

    await SagaStepBase._safe_compensate(ctx, "label-x", _action, sync=False)

    assert called == ["ran"]
    emit.assert_awaited()
    levels = [c.args[0] for c in emit.await_args_list]
    assert "info" in levels
    msgs = [c.args[1] for c in emit.await_args_list]
    assert any("compensate(label-x): ok" in m for m in msgs)


@pytest.mark.asyncio
async def test_safe_compensate_sync_runs_in_thread():
    ctx, emit = _make_ctx()
    called = []

    def _action():
        called.append("sync-ran")

    await SagaStepBase._safe_compensate(ctx, "sync-label", _action, sync=True)

    assert called == ["sync-ran"]
    msgs = [c.args[1] for c in emit.await_args_list]
    assert any("compensate(sync-label): ok" in m for m in msgs)


@pytest.mark.asyncio
async def test_safe_compensate_swallows_exception_and_warns():
    """Exception em compensate NAO propaga — saga rollback continua."""
    ctx, emit = _make_ctx()

    def _boom():
        raise RuntimeError("simulated failure")

    # NAO deve raise
    await SagaStepBase._safe_compensate(ctx, "broken", _boom, sync=True)

    # Deve emit warn
    levels = [c.args[0] for c in emit.await_args_list]
    msgs = [c.args[1] for c in emit.await_args_list]
    assert "warn" in levels
    assert any("compensate(broken) falhou" in m for m in msgs)
    assert any("simulated failure" in m for m in msgs)


@pytest.mark.asyncio
async def test_safe_compensate_continues_after_first_failure():
    """Multiplos compensates: se um falha, proximo ainda roda."""
    ctx, emit = _make_ctx()
    second_called = []

    def _first():
        raise ValueError("first fail")

    def _second():
        second_called.append("ran")

    await SagaStepBase._safe_compensate(ctx, "first", _first, sync=True)
    await SagaStepBase._safe_compensate(ctx, "second", _second, sync=True)

    assert second_called == ["ran"]
    msgs = [c.args[1] for c in emit.await_args_list]
    assert any("compensate(first) falhou" in m for m in msgs)
    assert any("compensate(second): ok" in m for m in msgs)
