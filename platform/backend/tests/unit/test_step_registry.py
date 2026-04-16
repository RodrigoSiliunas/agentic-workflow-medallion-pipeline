"""Testes do step registry do RealSagaRunner (T4 Phase 4)."""

from __future__ import annotations

import pytest

# Trigger import dos steps pra popular o registry
from app.services.real_saga import RealSagaRunner
from app.services.real_saga.registry import (
    STEP_REGISTRY,
    list_registered_steps,
    register_saga_step,
)


class TestRegistryPopulation:
    def test_all_ten_canonical_steps_registered(self):
        expected = {
            "validate",
            "s3",
            "iam",
            "secrets",
            "catalog",
            "upload",
            "observer",
            "workflow",
            "trigger",
            "register",
        }
        assert expected.issubset(set(STEP_REGISTRY.keys()))

    def test_list_registered_steps_sorted(self):
        listed = list_registered_steps()
        assert listed == sorted(listed)

    def test_each_entry_is_class_not_instance(self):
        for step_id, cls in STEP_REGISTRY.items():
            assert isinstance(cls, type), f"{step_id} should be a class"


class TestRegisterSagaStepDecorator:
    def test_decorator_inserts_into_registry(self):
        @register_saga_step("__test-step__")
        class _TestStep:
            step_id = "__test-step__"

            async def execute(self, ctx):  # noqa: ANN001
                pass

        try:
            assert STEP_REGISTRY["__test-step__"] is _TestStep
        finally:
            STEP_REGISTRY.pop("__test-step__", None)

    def test_decorator_sets_step_id_if_missing(self):
        @register_saga_step("__no-id-step__")
        class _NoIdStep:
            async def execute(self, ctx):  # noqa: ANN001
                pass

        try:
            assert _NoIdStep.step_id == "__no-id-step__"  # type: ignore[attr-defined]
        finally:
            STEP_REGISTRY.pop("__no-id-step__", None)

    def test_decorator_wins_over_divergent_class_attribute(self):
        @register_saga_step("__winner__")
        class _DivergentStep:
            step_id = "__loser__"

            async def execute(self, ctx):  # noqa: ANN001
                pass

        try:
            # Decorator fonte de verdade — sobrescreve
            assert _DivergentStep.step_id == "__winner__"
            assert "__winner__" in STEP_REGISTRY
            assert "__loser__" not in STEP_REGISTRY
        finally:
            STEP_REGISTRY.pop("__winner__", None)


class TestRunnerUsesRegistry:
    def test_runner_instantiates_all_registered_steps(self):
        runner = RealSagaRunner()
        for step_id in STEP_REGISTRY:
            assert step_id in runner._steps, f"{step_id} missing in runner"

    def test_runner_rejects_unknown_step_id(self):
        runner = RealSagaRunner()

        class _FakeCreds:
            aws_access_key_id = "x"
            aws_secret_access_key = "x"  # noqa: S105
            aws_region = "us-east-2"

        # execute_step e async — testamos raise via asyncio
        import asyncio
        from types import SimpleNamespace

        async def run():
            await runner.execute_step(
                deployment=SimpleNamespace(id="x", company_id="c", config={}),
                step_id="nonexistent-step",
                step_name="nope",
                emit_log=lambda *a, **kw: None,
                credentials=_FakeCreds(),
            )

        with pytest.raises(ValueError, match="step_id desconhecido"):
            asyncio.run(run())
