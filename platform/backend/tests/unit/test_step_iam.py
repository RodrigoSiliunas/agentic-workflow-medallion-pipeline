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
    ctx.warn = _noop_log
    return ctx


class TestEnsureBucketInPolicy:
    """Upsert da inline policy quando a role ja existe.

    Bug real: role compartilhada entre deploys cobria so o bucket do primeiro
    deploy; deploys com bucket novo falhavam com AccessDenied no write do UC.
    """

    def _fake_iam(self, monkeypatch, get_doc=None, get_exc=None):
        from app.services.real_saga.steps import iam as iam_mod

        fake = MagicMock()
        if get_exc is not None:
            fake.get_role_policy.side_effect = get_exc
        else:
            fake.get_role_policy.return_value = {"PolicyDocument": get_doc}
        session = MagicMock()
        session.client.return_value = fake
        monkeypatch.setattr(iam_mod, "boto3_session", lambda creds: session)
        return fake

    @pytest.mark.asyncio
    async def test_existing_role_without_policy_creates_it(self, monkeypatch):
        from botocore.exceptions import ClientError

        exc = ClientError({"Error": {"Code": "NoSuchEntity"}}, "GetRolePolicy")
        fake = self._fake_iam(monkeypatch, get_exc=exc)

        ctx = _make_ctx(env={"s3_bucket": "bucket-novo"})
        await IamStep._ensure_bucket_in_policy(ctx, "proj-uc-role")

        fake.put_role_policy.assert_called_once()
        doc = fake.put_role_policy.call_args.kwargs["PolicyDocument"]
        assert "arn:aws:s3:::bucket-novo" in doc

    @pytest.mark.asyncio
    async def test_existing_policy_merges_new_bucket(self, monkeypatch):
        doc = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": ["s3:GetObject", "s3:PutObject"],
                    "Resource": [
                        "arn:aws:s3:::bucket-antigo",
                        "arn:aws:s3:::bucket-antigo/*",
                    ],
                }
            ],
        }
        fake = self._fake_iam(monkeypatch, get_doc=doc)

        ctx = _make_ctx(env={"s3_bucket": "bucket-novo"})
        await IamStep._ensure_bucket_in_policy(ctx, "proj-uc-role")

        fake.put_role_policy.assert_called_once()
        import json

        merged = json.loads(fake.put_role_policy.call_args.kwargs["PolicyDocument"])
        resources = merged["Statement"][0]["Resource"]
        # Mantem o bucket antigo E adiciona o novo (bucket + objects)
        assert "arn:aws:s3:::bucket-antigo" in resources
        assert "arn:aws:s3:::bucket-novo" in resources
        assert "arn:aws:s3:::bucket-novo/*" in resources

    @pytest.mark.asyncio
    async def test_policy_already_covering_bucket_is_noop(self, monkeypatch):
        doc = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": ["s3:GetObject"],
                    "Resource": [
                        "arn:aws:s3:::bucket-atual",
                        "arn:aws:s3:::bucket-atual/*",
                    ],
                }
            ],
        }
        fake = self._fake_iam(monkeypatch, get_doc=doc)

        ctx = _make_ctx(env={"s3_bucket": "bucket-atual"})
        await IamStep._ensure_bucket_in_policy(ctx, "proj-uc-role")

        fake.put_role_policy.assert_not_called()

    @pytest.mark.asyncio
    async def test_without_bucket_in_context_skips(self, monkeypatch):
        from app.services.real_saga.steps import iam as iam_mod

        called = MagicMock()
        monkeypatch.setattr(
            iam_mod, "boto3_session", lambda creds: called() or MagicMock()
        )

        ctx = _make_ctx(env={})
        await IamStep._ensure_bucket_in_policy(ctx, "proj-uc-role")

        called.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_with_existing_role_upserts_policy(self, monkeypatch):
        """Caminho completo: role existe -> execute chama o upsert."""
        step = IamStep()
        upsert_calls: list[str] = []

        async def _fake_get(ctx, role_name):
            return "arn:aws:iam::111111111111:role/existing"

        async def _fake_ensure(ctx, role_name):
            upsert_calls.append(role_name)

        monkeypatch.setattr(IamStep, "_get_role", staticmethod(_fake_get))
        monkeypatch.setattr(
            IamStep, "_ensure_bucket_in_policy", staticmethod(_fake_ensure)
        )

        ctx = _make_ctx(env={"project_name": "acme-pipeline"})
        await step.execute(ctx)

        assert upsert_calls == ["acme-pipeline-uc-role"]
