"""Unit tests para ClusterProvisionStep — sizing override via env vars."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.real_saga.base import (
    DeploymentCredentials,
    SharedSagaState,
    StepContext,
)
from app.services.real_saga.steps.cluster_provision import ClusterProvisionStep


def _make_ctx(env_vars: dict[str, str] | None = None) -> StepContext:
    dep = MagicMock()
    dep.id = uuid.uuid4()
    dep.company_id = uuid.uuid4()
    dep.config = {"env_vars": env_vars or {}}
    return StepContext(
        deployment=dep,
        step_id="cluster_provision",
        step_name="Cluster Provision",
        credentials=DeploymentCredentials(
            aws_access_key_id="AKIA",
            aws_secret_access_key="sec",
            aws_region="us-east-2",
            databricks_host="https://dbc.cloud.databricks.com",
            databricks_token="dapi",
        ),
        emit_log=AsyncMock(),
        state_dir=MagicMock(),
        shared=SharedSagaState(),
    )


class TestClusterSizingOverride:
    @pytest.mark.asyncio
    async def test_explicit_cluster_id_skips_sizing(self):
        """env_vars[cluster_id] != "" -> usa direto sem criar."""
        ctx = _make_ctx(env_vars={"cluster_id": "abc-123-def"})
        step = ClusterProvisionStep()
        await step.execute(ctx)
        assert ctx.shared.databricks_cluster_id == "abc-123-def"

    @pytest.mark.asyncio
    async def test_default_node_type_when_unset(self, monkeypatch):
        """Sem cluster_node_type -> defaults pra m5d.large + 2 workers."""
        captured: dict = {}

        async def fake_ensure(
            ctx, w, scope, region, admin_email,
            node_type="m5d.large",
            num_workers=2,
            spark_version="15.4.x-scala2.12",
        ):
            captured["node_type"] = node_type
            captured["num_workers"] = num_workers
            captured["spark_version"] = spark_version
            return "fake-cluster-id"

        monkeypatch.setattr(
            ClusterProvisionStep, "_ensure_cluster", staticmethod(fake_ensure)
        )
        monkeypatch.setattr(
            "app.services.real_saga.steps.cluster_provision.workspace_client",
            lambda creds: MagicMock(),
        )

        ctx = _make_ctx(env_vars={})
        step = ClusterProvisionStep()
        await step.execute(ctx)

        assert captured["node_type"] == "m5d.large"
        assert captured["num_workers"] == 2
        assert captured["spark_version"] == "15.4.x-scala2.12"

    @pytest.mark.asyncio
    async def test_override_via_env_vars(self, monkeypatch):
        """env_vars custom propagados pra _ensure_cluster."""
        captured: dict = {}

        async def fake_ensure(
            ctx, w, scope, region, admin_email,
            node_type="m5d.large",
            num_workers=2,
            spark_version="15.4.x-scala2.12",
        ):
            captured["node_type"] = node_type
            captured["num_workers"] = num_workers
            captured["spark_version"] = spark_version
            return "fake-cluster-id"

        monkeypatch.setattr(
            ClusterProvisionStep, "_ensure_cluster", staticmethod(fake_ensure)
        )
        monkeypatch.setattr(
            "app.services.real_saga.steps.cluster_provision.workspace_client",
            lambda creds: MagicMock(),
        )

        ctx = _make_ctx(env_vars={
            "cluster_node_type": "r5d.2xlarge",
            "cluster_num_workers": "4",
            "cluster_spark_version": "16.1.x-scala2.12",
        })
        step = ClusterProvisionStep()
        await step.execute(ctx)

        assert captured["node_type"] == "r5d.2xlarge"
        assert captured["num_workers"] == 4
        assert captured["spark_version"] == "16.1.x-scala2.12"

    @pytest.mark.asyncio
    async def test_invalid_num_workers_falls_back_to_default(self, monkeypatch):
        """num_workers nao-int -> default 2 (resiliente a input ruim)."""
        captured: dict = {}

        async def fake_ensure(
            ctx, w, scope, region, admin_email,
            node_type="m5d.large",
            num_workers=2,
            spark_version="15.4.x-scala2.12",
        ):
            captured["num_workers"] = num_workers
            return "fake-cluster-id"

        monkeypatch.setattr(
            ClusterProvisionStep, "_ensure_cluster", staticmethod(fake_ensure)
        )
        monkeypatch.setattr(
            "app.services.real_saga.steps.cluster_provision.workspace_client",
            lambda creds: MagicMock(),
        )

        ctx = _make_ctx(env_vars={"cluster_num_workers": "not-a-number"})
        step = ClusterProvisionStep()
        await step.execute(ctx)

        assert captured["num_workers"] == 2
