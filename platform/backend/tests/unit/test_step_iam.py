"""Unit tests para IamStep + trust policy helper."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.real_saga.steps.iam import (
    _UC_MASTER_ROLE_ARN,
    IamStep,
    _build_trust_policy,
)


class TestTrustPolicy:
    def test_bootstrap_principal_is_ucmasterrole_only(self):
        """Bootstrap: UCMasterRole apenas, sem external_id, sem self-ref."""
        policy = _build_trust_policy()
        stmt = policy["Statement"][0]
        assert stmt["Effect"] == "Allow"
        assert stmt["Action"] == "sts:AssumeRole"
        assert stmt["Principal"]["AWS"] == _UC_MASTER_ROLE_ARN
        assert "Condition" not in stmt

    def test_final_principal_includes_self_role(self):
        """Final: UCMasterRole + self-role (self-assuming pattern UC)."""
        role = "arn:aws:iam::111:role/my-role"
        policy = _build_trust_policy(external_id="ext-id", self_role_arn=role)
        stmt = policy["Statement"][0]
        assert isinstance(stmt["Principal"]["AWS"], list)
        assert _UC_MASTER_ROLE_ARN in stmt["Principal"]["AWS"]
        assert role in stmt["Principal"]["AWS"]

    def test_final_has_external_id_condition(self):
        role = "arn:aws:iam::111:role/my-role"
        policy = _build_trust_policy(external_id="abc123", self_role_arn=role)
        stmt = policy["Statement"][0]
        assert stmt["Condition"] == {
            "StringEquals": {"sts:ExternalId": "abc123"}
        }

    def test_different_external_ids_produce_different_policies(self):
        role = "arn:aws:iam::111:role/r"
        a = _build_trust_policy(external_id="id-a", self_role_arn=role)
        b = _build_trust_policy(external_id="id-b", self_role_arn=role)
        assert a != b


class TestIamStepBootstrap:
    @pytest.mark.asyncio
    async def test_execute_creates_role_without_condition_when_new(
        self, monkeypatch
    ):
        """iam step NAO define external_id no trust. catalog step faz depois."""
        step = IamStep()

        async def _fake_get(ctx, role_name):
            return None  # role nao existe

        async def _fake_create(ctx, role_name):
            return f"arn:aws:iam::111111111111:role/{role_name}"

        monkeypatch.setattr(IamStep, "_get_role", staticmethod(_fake_get))
        monkeypatch.setattr(IamStep, "_create_role", staticmethod(_fake_create))

        ctx = _make_ctx(env={"project_name": "acme-pipeline"})
        await step.execute(ctx)

        assert ctx.shared.databricks_role_arn.endswith(
            "/acme-pipeline-uc-role"
        )
        # iam step NAO seta external_id — quem faz e catalog step apos
        # criar Storage Credential
        assert ctx.shared.databricks_external_id is None

    @pytest.mark.asyncio
    async def test_execute_reuses_existing_role(self, monkeypatch):
        step = IamStep()
        create_calls = 0

        async def _fake_get(ctx, role_name):
            return "arn:aws:iam::111111111111:role/existing"

        async def _fake_create(ctx, role_name):
            nonlocal create_calls
            create_calls += 1
            return "never-reached"

        monkeypatch.setattr(IamStep, "_get_role", staticmethod(_fake_get))
        monkeypatch.setattr(IamStep, "_create_role", staticmethod(_fake_create))

        ctx = _make_ctx(env={"project_name": "acme-pipeline"})
        await step.execute(ctx)

        assert create_calls == 0
        assert ctx.shared.databricks_role_arn == (
            "arn:aws:iam::111111111111:role/existing"
        )


def _make_ctx(env: dict[str, str]):
    """Context mínimo pro IamStep.execute."""
    from app.services.real_saga.base import (
        DeploymentCredentials,
        SharedSagaState,
    )

    ctx = MagicMock()
    ctx.env_vars.return_value = env
    ctx.credentials = DeploymentCredentials(
        aws_access_key_id="AKIA",
        aws_secret_access_key="sec",
        aws_region="us-east-2",
    )
    ctx.shared = SharedSagaState()

    async def _noop_log(*args, **kwargs):
        return None

    ctx.info = _noop_log
    ctx.success = _noop_log
    return ctx
