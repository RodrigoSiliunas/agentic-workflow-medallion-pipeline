"""Unit tests para a interface pluggable dos saga runners."""

from unittest.mock import AsyncMock

import pytest

from app.services.saga_runners import (
    MOCK_STEP_LOGS,
    RUNNER_REGISTRY,
    MockSagaRunner,
    get_runner,
)


def test_registry_has_mock_runner():
    assert "mock" in RUNNER_REGISTRY


def test_get_runner_returns_mock_by_default(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "SAGA_RUNNER", "mock")
    runner = get_runner()
    assert isinstance(runner, MockSagaRunner)


def test_get_runner_accepts_real(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "SAGA_RUNNER", "real")
    runner = get_runner()
    # RealSagaRunner e resolvido lazy — so checamos que foi criado
    assert runner.name == "real"
    assert hasattr(runner, "execute_step")


def test_get_runner_falls_back_to_mock_on_unknown(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "SAGA_RUNNER", "k8s-jobs")
    runner = get_runner()
    assert isinstance(runner, MockSagaRunner)


@pytest.mark.asyncio
async def test_mock_runner_emits_logs_per_step():
    runner = MockSagaRunner()
    emit = AsyncMock()

    await runner.execute_step(
        deployment=None,  # type: ignore[arg-type]
        step_id="validate",
        step_name="Validate credentials",
        emit_log=emit,
    )

    # Esperamos pelo menos um emit por mensagem mockada
    expected_min = len(MOCK_STEP_LOGS["validate"])
    assert emit.await_count >= expected_min
    # Todas as calls recebem step_id="validate"
    for call in emit.await_args_list:
        args = call.args
        assert args[0] in ("info", "warn")
        assert isinstance(args[1], str)
        assert args[2] == "validate"
