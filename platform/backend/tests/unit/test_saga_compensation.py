"""Testes de compensating actions no RealSagaRunner (T4 Phase 1+2)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.services.real_saga.runner import RealSagaRunner


class _FakeStep:
    def __init__(self, step_id: str):
        self.step_id = step_id
        self.executed = False
        self.compensated = False
        self.execute_should_raise = False
        self.compensate_should_raise = False

    async def execute(self, ctx):  # noqa: ANN001
        self.executed = True
        if self.execute_should_raise:
            raise RuntimeError(f"boom-{self.step_id}")

    async def compensate(self, ctx):  # noqa: ANN001
        self.compensated = True
        if self.compensate_should_raise:
            raise RuntimeError(f"compensate-boom-{self.step_id}")


def _make_runner_with_steps(*step_ids: str) -> tuple[RealSagaRunner, dict[str, _FakeStep]]:
    runner = RealSagaRunner()
    runner._steps = {sid: _FakeStep(sid) for sid in step_ids}
    return runner, runner._steps  # type: ignore[return-value]


def _make_deployment(dep_id: str | None = None):
    return SimpleNamespace(
        id=uuid.UUID(dep_id or "11111111-1111-1111-1111-111111111111"),
        company_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        config={},
    )


class _FakeCredentials:
    """Credenciais minimas pra satisfazer o Runner."""

    aws_access_key_id = "AKIA"  # noqa: S105
    aws_secret_access_key = "sec"  # noqa: S105
    aws_region = "us-east-2"


@pytest.mark.asyncio
async def test_compensation_runs_completed_steps_in_reverse(tmp_path, monkeypatch):
    runner, steps = _make_runner_with_steps("s3", "iam", "secrets")
    monkeypatch.setattr(
        "app.services.real_saga.runner._state_dir_for",
        lambda _d: tmp_path,
    )

    deployment = _make_deployment()
    dep_key = str(deployment.id)

    async def emit_log(level, msg, step_id=None):
        return None

    for step_id in ("s3", "iam"):
        await runner.execute_step(
            deployment=deployment,
            step_id=step_id,
            step_name=step_id,
            emit_log=emit_log,
            credentials=_FakeCredentials(),
        )

    assert steps["s3"].executed
    assert steps["iam"].executed
    assert not steps["secrets"].executed

    call_order: list[str] = []
    original_compensate_s3 = steps["s3"].compensate
    original_compensate_iam = steps["iam"].compensate

    async def spy_s3(ctx):
        call_order.append("s3")
        await original_compensate_s3(ctx)

    async def spy_iam(ctx):
        call_order.append("iam")
        await original_compensate_iam(ctx)

    steps["s3"].compensate = spy_s3  # type: ignore[assignment]
    steps["iam"].compensate = spy_iam  # type: ignore[assignment]

    await runner.run_compensation(dep_key)
    # iam deve compensate primeiro (foi executado depois)
    assert call_order == ["iam", "s3"]


@pytest.mark.asyncio
async def test_compensation_continues_despite_one_step_raising(tmp_path, monkeypatch):
    runner, steps = _make_runner_with_steps("s3", "iam")
    monkeypatch.setattr(
        "app.services.real_saga.runner._state_dir_for",
        lambda _d: tmp_path,
    )
    deployment = _make_deployment()
    dep_key = str(deployment.id)

    async def emit_log(level, msg, step_id=None):
        return None

    for step_id in ("s3", "iam"):
        await runner.execute_step(
            deployment=deployment,
            step_id=step_id,
            step_name=step_id,
            emit_log=emit_log,
            credentials=_FakeCredentials(),
        )

    steps["iam"].compensate_should_raise = True

    # Nao deve propagar — log warn + segue pra s3
    await runner.run_compensation(dep_key)
    assert steps["iam"].compensated
    assert steps["s3"].compensated


@pytest.mark.asyncio
async def test_compensation_skips_steps_without_compensate(tmp_path, monkeypatch):
    runner = RealSagaRunner()
    # Step sem compensate (legacy)

    class _LegacyStep:
        step_id = "legacy"

        def __init__(self):
            self.executed = False

        async def execute(self, ctx):  # noqa: ANN001
            self.executed = True

    runner._steps = {"legacy": _LegacyStep()}
    monkeypatch.setattr(
        "app.services.real_saga.runner._state_dir_for",
        lambda _d: tmp_path,
    )

    deployment = _make_deployment()

    async def emit_log(level, msg, step_id=None):
        return None

    await runner.execute_step(
        deployment=deployment,
        step_id="legacy",
        step_name="legacy",
        emit_log=emit_log,
        credentials=_FakeCredentials(),
    )

    # Nao deve raise — apenas skip
    await runner.run_compensation(str(deployment.id))


@pytest.mark.asyncio
async def test_cleanup_shared_state_removes_shared_and_completed(tmp_path, monkeypatch):
    runner, _ = _make_runner_with_steps("s3")
    monkeypatch.setattr(
        "app.services.real_saga.runner._state_dir_for",
        lambda _d: tmp_path,
    )
    deployment = _make_deployment()
    dep_key = str(deployment.id)

    async def emit_log(level, msg, step_id=None):
        return None

    await runner.execute_step(
        deployment=deployment,
        step_id="s3",
        step_name="s3",
        emit_log=emit_log,
        credentials=_FakeCredentials(),
    )
    assert dep_key in runner._shared_per_deployment
    assert dep_key in runner._completed_per_deployment

    runner.cleanup_shared_state(dep_key)
    assert dep_key not in runner._shared_per_deployment
    assert dep_key not in runner._completed_per_deployment


@pytest.mark.asyncio
async def test_failed_step_not_added_to_completed(tmp_path, monkeypatch):
    runner, steps = _make_runner_with_steps("s3", "iam")
    monkeypatch.setattr(
        "app.services.real_saga.runner._state_dir_for",
        lambda _d: tmp_path,
    )
    deployment = _make_deployment()
    dep_key = str(deployment.id)

    async def emit_log(level, msg, step_id=None):
        return None

    await runner.execute_step(
        deployment=deployment,
        step_id="s3",
        step_name="s3",
        emit_log=emit_log,
        credentials=_FakeCredentials(),
    )

    steps["iam"].execute_should_raise = True
    with pytest.raises(RuntimeError):
        await runner.execute_step(
            deployment=deployment,
            step_id="iam",
            step_name="iam",
            emit_log=emit_log,
            credentials=_FakeCredentials(),
        )

    # Apenas s3 deve estar no historico — iam falhou em execute
    completed_ids = [sid for sid, _ in runner._completed_per_deployment[dep_key]]
    assert completed_ids == ["s3"]


@pytest.mark.asyncio
async def test_compensation_noop_when_no_completed_steps():
    runner, _ = _make_runner_with_steps("s3")
    await runner.run_compensation("nonexistent-id")
