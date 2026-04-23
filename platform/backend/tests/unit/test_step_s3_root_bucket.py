"""Unit tests para s3 step focando no fluxo de root bucket adicional."""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.real_saga.base import (
    DeploymentCredentials,
    SharedSagaState,
    StepContext,
)
from app.services.real_saga.steps.s3 import (
    _DATABRICKS_AWS_ACCOUNT,
    S3Step,
    _resolve_root_bucket_name,
)


def _make_ctx(env_vars: dict[str, str] | None = None) -> StepContext:
    dep = MagicMock()
    dep.id = uuid.uuid4()
    dep.company_id = uuid.uuid4()
    dep.config = {"env_vars": env_vars or {}}
    return StepContext(
        deployment=dep,
        step_id="s3",
        step_name="S3 Buckets",
        credentials=DeploymentCredentials(
            aws_access_key_id="AKIA",
            aws_secret_access_key="secret",
            aws_region="us-east-2",
        ),
        emit_log=AsyncMock(),
        state_dir=MagicMock(),
        shared=SharedSagaState(),
    )


class TestRootBucketResolution:
    def test_default_derivation(self):
        ctx = _make_ctx()
        assert _resolve_root_bucket_name(ctx, "my-data") == "my-data-root"

    def test_override_via_env_var(self):
        ctx = _make_ctx(env_vars={"workspace_root_bucket": "custom-name"})
        assert _resolve_root_bucket_name(ctx, "my-data") == "custom-name"

    def test_empty_override_falls_back_to_default(self):
        ctx = _make_ctx(env_vars={"workspace_root_bucket": "   "})
        assert _resolve_root_bucket_name(ctx, "my-data") == "my-data-root"


class TestApplyDatabricksRootPolicy:
    @pytest.mark.asyncio
    @patch("app.services.real_saga.steps.s3.boto3_session")
    async def test_policy_grants_databricks_principal(self, mock_session):
        """Bucket policy permite Databricks AWS account principal."""
        ctx = _make_ctx()

        s3_client = MagicMock()
        session = MagicMock()
        session.client.return_value = s3_client
        mock_session.return_value = session

        await S3Step._apply_databricks_root_policy(ctx, "my-root-bucket")

        s3_client.put_bucket_policy.assert_called_once()
        kwargs = s3_client.put_bucket_policy.call_args.kwargs
        assert kwargs["Bucket"] == "my-root-bucket"
        policy = json.loads(kwargs["Policy"])
        stmt = policy["Statement"][0]
        assert stmt["Principal"]["AWS"] == (
            f"arn:aws:iam::{_DATABRICKS_AWS_ACCOUNT}:root"
        )
        assert "s3:GetObject" in stmt["Action"]
        assert "arn:aws:s3:::my-root-bucket/*" in stmt["Resource"]


class TestS3StepDualBucket:
    @pytest.mark.asyncio
    @patch("app.services.real_saga.steps.s3.boto3_session")
    async def test_creates_both_buckets_when_neither_exists(self, mock_session):
        """Caminho feliz: cria datalake + root + aplica policy."""
        ctx = _make_ctx(env_vars={"s3_bucket": "flowertex-datalake"})
        step = S3Step()

        s3_client = MagicMock()
        # head_bucket sempre raises NotFound -> branch criar
        from botocore.exceptions import ClientError

        not_found = ClientError(
            {"Error": {"Code": "404"}}, "HeadBucket"
        )
        s3_client.head_bucket.side_effect = not_found

        session = MagicMock()
        session.client.return_value = s3_client
        mock_session.return_value = session

        await step.execute(ctx)

        # 2 create_bucket calls (datalake + root)
        assert s3_client.create_bucket.call_count == 2
        bucket_names = [
            call.kwargs["Bucket"]
            for call in s3_client.create_bucket.call_args_list
        ]
        assert "flowertex-datalake" in bucket_names
        assert "flowertex-datalake-root" in bucket_names

        # Policy aplicada no root
        s3_client.put_bucket_policy.assert_called_once()
        assert s3_client.put_bucket_policy.call_args.kwargs["Bucket"] == (
            "flowertex-datalake-root"
        )

        assert ctx.shared.s3_bucket == "flowertex-datalake"
        assert ctx.shared.workspace_root_bucket == "flowertex-datalake-root"

    @pytest.mark.asyncio
    @patch("app.services.real_saga.steps.s3.boto3_session")
    async def test_root_bucket_skips_medallion_prefixes(self, mock_session):
        """Root bucket nao deve receber pastas bronze/silver/gold."""
        ctx = _make_ctx(env_vars={"s3_bucket": "my-data"})
        step = S3Step()

        s3_client = MagicMock()
        from botocore.exceptions import ClientError

        s3_client.head_bucket.side_effect = ClientError(
            {"Error": {"Code": "404"}}, "HeadBucket"
        )
        session = MagicMock()
        session.client.return_value = s3_client
        mock_session.return_value = session

        await step.execute(ctx)

        # put_object com prefixes so deve rodar pro datalake (5 prefixos)
        # Root bucket = 0 puts. Total = 5.
        prefix_puts = [
            c for c in s3_client.put_object.call_args_list
            if c.kwargs.get("Bucket") == "my-data"
        ]
        root_puts = [
            c for c in s3_client.put_object.call_args_list
            if c.kwargs.get("Bucket") == "my-data-root"
        ]
        assert len(prefix_puts) == 5  # bronze/silver/gold/pipeline/checkpoints
        assert len(root_puts) == 0

    @pytest.mark.asyncio
    @patch("app.services.real_saga.steps.s3.boto3_session")
    async def test_reuses_existing_buckets(self, mock_session):
        """head_bucket OK = nao cria, mas ainda aplica policy no root."""
        ctx = _make_ctx(env_vars={"s3_bucket": "existing-data"})
        step = S3Step()

        s3_client = MagicMock()
        s3_client.head_bucket.return_value = {}  # exists
        session = MagicMock()
        session.client.return_value = s3_client
        mock_session.return_value = session

        await step.execute(ctx)

        s3_client.create_bucket.assert_not_called()
        # Policy continua sendo aplicada (idempotente)
        s3_client.put_bucket_policy.assert_called_once()
        assert ctx.shared.workspace_root_bucket == "existing-data-root"
