"""Unit tests para WorkspaceProvisionStep no modo workspace_mode=existing."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.real_saga.base import (
    DeploymentCredentials,
    SharedSagaState,
    StepContext,
)
from app.services.real_saga.steps.workspace_provision import (
    WorkspaceProvisionStep,
)


def _make_ctx(env_vars: dict[str, str]) -> StepContext:
    dep = MagicMock()
    dep.id = uuid.uuid4()
    dep.company_id = uuid.uuid4()
    dep.config = {"env_vars": env_vars}
    return StepContext(
        deployment=dep,
        step_id="workspace_provision",
        step_name="Workspace Provision",
        credentials=DeploymentCredentials(
            aws_region="us-east-2",
        ),
        emit_log=AsyncMock(),
        state_dir=MagicMock(),
        shared=SharedSagaState(),
    )


class TestExistingWorkspaceMode:
    @pytest.mark.asyncio
    async def test_existing_mode_requires_workspace_id(self):
        step = WorkspaceProvisionStep()
        ctx = _make_ctx(env_vars={
            "workspace_mode": "existing",
            "databricks_account_id": "acc",
            "databricks_oauth_client_id": "c",
            "databricks_oauth_secret": "s",
        })
        with pytest.raises(RuntimeError, match="workspace_id"):
            await step.execute(ctx)

    @pytest.mark.asyncio
    @patch("app.services.real_saga.steps.workspace_provision.httpx.AsyncClient")
    async def test_existing_mode_hydrates_shared_state(self, mock_client_cls):
        """Modo existing pega config do workspace e popula shared."""
        step = WorkspaceProvisionStep()
        ctx = _make_ctx(env_vars={
            "workspace_mode": "existing",
            "workspace_id": "12345",
            "databricks_account_id": "acc",
            "databricks_oauth_client_id": "c",
            "databricks_oauth_secret": "s",
        })

        client_mock = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = client_mock

        # Token
        token_resp = MagicMock()
        token_resp.json.return_value = {"access_token": "tok"}
        token_resp.raise_for_status = MagicMock()

        # Workspace fetch
        ws_resp = MagicMock()
        ws_resp.json.return_value = {
            "workspace_id": 12345,
            "workspace_status": "RUNNING",
            "workspace_fqdn": "dbc-test.cloud.databricks.com",
            "network_id": "net-existing",
            "credentials_id": "cred-existing",
            "storage_configuration_id": "sc-existing",
        }
        ws_resp.raise_for_status = MagicMock()

        # PAT generation -> sucesso
        pat_resp = MagicMock()
        pat_resp.status_code = 200
        pat_resp.json.return_value = {"token_value": "dapi-fresh"}

        client_mock.post.side_effect = [token_resp, pat_resp]
        client_mock.get.return_value = ws_resp

        await step.execute(ctx)

        assert ctx.shared.databricks_workspace_id == 12345
        assert ctx.shared.databricks_network_id == "net-existing"
        assert ctx.shared.databricks_credentials_id == "cred-existing"
        assert ctx.shared.databricks_storage_config_id == "sc-existing"
        assert ctx.credentials.databricks_token == "dapi-fresh"
        assert ctx.credentials.databricks_host == (
            "https://dbc-test.cloud.databricks.com"
        )

    @pytest.mark.asyncio
    @patch("app.services.real_saga.steps.workspace_provision.httpx.AsyncClient")
    async def test_existing_mode_rejects_non_running(self, mock_client_cls):
        step = WorkspaceProvisionStep()
        ctx = _make_ctx(env_vars={
            "workspace_mode": "existing",
            "workspace_id": "12345",
            "databricks_account_id": "acc",
            "databricks_oauth_client_id": "c",
            "databricks_oauth_secret": "s",
        })

        client_mock = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = client_mock

        token_resp = MagicMock()
        token_resp.json.return_value = {"access_token": "tok"}
        token_resp.raise_for_status = MagicMock()

        ws_resp = MagicMock()
        ws_resp.json.return_value = {
            "workspace_id": 12345,
            "workspace_status": "FAILED",
        }
        ws_resp.raise_for_status = MagicMock()

        client_mock.post.return_value = token_resp
        client_mock.get.return_value = ws_resp

        with pytest.raises(RuntimeError, match="status=FAILED"):
            await step.execute(ctx)
