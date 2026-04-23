"""Unit tests para MetastoreAssignStep."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.real_saga.base import (
    DeploymentCredentials,
    SharedSagaState,
    StepContext,
)
from app.services.real_saga.steps.metastore_assign import MetastoreAssignStep


def _make_ctx(
    env_vars: dict[str, str] | None = None,
    shared: SharedSagaState | None = None,
) -> StepContext:
    dep = MagicMock()
    dep.id = uuid.uuid4()
    dep.company_id = uuid.uuid4()
    dep.config = {"env_vars": env_vars or {}}
    return StepContext(
        deployment=dep,
        step_id="metastore_assign",
        step_name="Metastore Assign",
        credentials=DeploymentCredentials(aws_region="us-east-2"),
        emit_log=AsyncMock(),
        state_dir=MagicMock(),
        shared=shared or SharedSagaState(),
    )


class TestMetastoreAssign:
    @pytest.mark.asyncio
    async def test_skip_when_oauth_missing(self):
        step = MetastoreAssignStep()
        ctx = _make_ctx(env_vars={})
        await step.execute(ctx)
        warn_calls = [
            c.args[1] for c in ctx.emit_log.call_args_list if c.args[0] == "warn"
        ]
        assert any("OAuth" in m for m in warn_calls)

    @pytest.mark.asyncio
    async def test_raise_when_workspace_id_missing(self):
        step = MetastoreAssignStep()
        ctx = _make_ctx(env_vars={
            "databricks_account_id": "acc",
            "databricks_oauth_client_id": "c",
            "databricks_oauth_secret": "s",
        })
        with pytest.raises(RuntimeError, match="databricks_workspace_id"):
            await step.execute(ctx)

    @pytest.mark.asyncio
    @patch("app.services.real_saga.steps.metastore_assign.httpx.AsyncClient")
    async def test_attaches_when_unattached(self, mock_client_cls):
        """Workspace nao attached -> PUT pra metastore."""
        step = MetastoreAssignStep()
        shared = SharedSagaState(databricks_workspace_id=12345)
        ctx = _make_ctx(
            env_vars={
                "databricks_account_id": "acc",
                "databricks_oauth_client_id": "c",
                "databricks_oauth_secret": "s",
                "databricks_metastore_id": "ms-explicit",
                "catalog": "medallion",
            },
            shared=shared,
        )

        client_mock = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = client_mock

        token_resp = MagicMock()
        token_resp.json.return_value = {"access_token": "tok"}
        token_resp.raise_for_status = MagicMock()
        client_mock.post.return_value = token_resp

        # GET current attachment -> 404 (nao attached)
        current_resp = MagicMock()
        current_resp.status_code = 404
        client_mock.get.return_value = current_resp

        # PUT attach
        put_resp = MagicMock()
        put_resp.raise_for_status = MagicMock()
        client_mock.put.return_value = put_resp

        await step.execute(ctx)

        assert ctx.shared.databricks_metastore_id == "ms-explicit"
        client_mock.put.assert_called_once()
        put_body = client_mock.put.call_args.kwargs["json"]
        assert put_body["metastore_id"] == "ms-explicit"
        assert put_body["default_catalog_name"] == "medallion"

    @pytest.mark.asyncio
    @patch("app.services.real_saga.steps.metastore_assign.httpx.AsyncClient")
    async def test_skips_when_already_attached_to_same(self, mock_client_cls):
        """Workspace ja attached ao metastore correto -> no-op."""
        step = MetastoreAssignStep()
        shared = SharedSagaState(databricks_workspace_id=12345)
        ctx = _make_ctx(
            env_vars={
                "databricks_account_id": "acc",
                "databricks_oauth_client_id": "c",
                "databricks_oauth_secret": "s",
                "databricks_metastore_id": "ms-1",
            },
            shared=shared,
        )

        client_mock = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = client_mock

        token_resp = MagicMock()
        token_resp.json.return_value = {"access_token": "tok"}
        token_resp.raise_for_status = MagicMock()
        client_mock.post.return_value = token_resp

        current_resp = MagicMock()
        current_resp.status_code = 200
        current_resp.json.return_value = {"metastore_id": "ms-1"}
        client_mock.get.return_value = current_resp

        await step.execute(ctx)
        client_mock.put.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.services.real_saga.steps.metastore_assign.httpx.AsyncClient")
    async def test_raises_when_attached_to_different(self, mock_client_cls):
        step = MetastoreAssignStep()
        shared = SharedSagaState(databricks_workspace_id=12345)
        ctx = _make_ctx(
            env_vars={
                "databricks_account_id": "acc",
                "databricks_oauth_client_id": "c",
                "databricks_oauth_secret": "s",
                "databricks_metastore_id": "ms-target",
            },
            shared=shared,
        )

        client_mock = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = client_mock

        token_resp = MagicMock()
        token_resp.json.return_value = {"access_token": "tok"}
        token_resp.raise_for_status = MagicMock()
        client_mock.post.return_value = token_resp

        current_resp = MagicMock()
        current_resp.status_code = 200
        current_resp.json.return_value = {"metastore_id": "ms-other"}
        client_mock.get.return_value = current_resp

        with pytest.raises(RuntimeError, match="OUTRO metastore"):
            await step.execute(ctx)

    @pytest.mark.asyncio
    @patch("app.services.real_saga.steps.metastore_assign.httpx.AsyncClient")
    async def test_auto_discover_metastore(self, mock_client_cls):
        """Sem metastore_id -> faz GET /metastores e filtra por regiao."""
        step = MetastoreAssignStep()
        shared = SharedSagaState(databricks_workspace_id=12345)
        ctx = _make_ctx(
            env_vars={
                "databricks_account_id": "acc",
                "databricks_oauth_client_id": "c",
                "databricks_oauth_secret": "s",
            },
            shared=shared,
        )

        client_mock = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = client_mock

        token_resp = MagicMock()
        token_resp.json.return_value = {"access_token": "tok"}
        token_resp.raise_for_status = MagicMock()
        client_mock.post.return_value = token_resp

        # Discover
        discover_resp = MagicMock()
        discover_resp.json.return_value = {
            "metastores": [
                {"metastore_id": "ms-other-region", "region": "us-west-2", "name": "wrong"},
                {"metastore_id": "ms-correct", "region": "us-east-2", "name": "right"},
            ]
        }
        discover_resp.raise_for_status = MagicMock()

        # Current attachment
        current_resp = MagicMock()
        current_resp.status_code = 404

        client_mock.get.side_effect = [discover_resp, current_resp]

        put_resp = MagicMock()
        put_resp.raise_for_status = MagicMock()
        client_mock.put.return_value = put_resp

        await step.execute(ctx)

        assert ctx.shared.databricks_metastore_id == "ms-correct"
