"""Unit tests para StorageConfigurationStep."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.real_saga.base import (
    DeploymentCredentials,
    SharedSagaState,
    StepContext,
)
from app.services.real_saga.steps.storage_configuration import (
    StorageConfigurationStep,
)


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
        step_id="storage_configuration",
        step_name="Storage Configuration",
        credentials=DeploymentCredentials(aws_region="us-east-2"),
        emit_log=AsyncMock(),
        state_dir=MagicMock(),
        shared=shared or SharedSagaState(),
    )


class TestStorageConfiguration:
    @pytest.mark.asyncio
    async def test_skip_when_oauth_missing(self):
        """Sem OAuth M2M = warn + skip silencioso (preserva compat)."""
        step = StorageConfigurationStep()
        ctx = _make_ctx(env_vars={})
        await step.execute(ctx)
        warn_calls = [
            c.args[1] for c in ctx.emit_log.call_args_list if c.args[0] == "warn"
        ]
        assert any("OAuth" in m for m in warn_calls)
        assert ctx.shared.databricks_storage_config_id is None

    @pytest.mark.asyncio
    async def test_raise_when_root_bucket_missing(self):
        """OAuth presente + root_bucket ausente = RuntimeError (s3 step deve rodar antes)."""
        step = StorageConfigurationStep()
        ctx = _make_ctx(env_vars={
            "databricks_account_id": "acc-1",
            "databricks_oauth_client_id": "client-1",
            "databricks_oauth_secret": "secret-1",
        })
        with pytest.raises(RuntimeError, match="workspace_root_bucket"):
            await step.execute(ctx)

    @pytest.mark.asyncio
    @patch("app.services.real_saga.steps.storage_configuration.httpx.AsyncClient")
    async def test_creates_when_not_exists(self, mock_client_cls):
        """POST cria storage configuration quando lookup retorna lista vazia."""
        step = StorageConfigurationStep()
        shared = SharedSagaState(workspace_root_bucket="my-root-bucket")
        ctx = _make_ctx(
            env_vars={
                "databricks_account_id": "acc-1",
                "databricks_oauth_client_id": "client-1",
                "databricks_oauth_secret": "secret-1",
                "project_name": "flowertex",
            },
            shared=shared,
        )

        client_mock = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = client_mock

        # OAuth token
        token_resp = MagicMock()
        token_resp.json.return_value = {"access_token": "tok-1"}
        token_resp.raise_for_status = MagicMock()

        # List existing — vazio
        list_resp = MagicMock()
        list_resp.json.return_value = []
        list_resp.raise_for_status = MagicMock()

        # Create
        create_resp = MagicMock()
        create_resp.json.return_value = {"storage_configuration_id": "sc-new-123"}
        create_resp.raise_for_status = MagicMock()

        client_mock.post.side_effect = [token_resp, create_resp]
        client_mock.get.return_value = list_resp

        await step.execute(ctx)

        assert ctx.shared.databricks_storage_config_id == "sc-new-123"
        # Verifica payload do POST
        create_call = client_mock.post.call_args_list[1]
        body = create_call.kwargs["json"]
        assert body["root_bucket_info"]["bucket_name"] == "my-root-bucket"

    @pytest.mark.asyncio
    @patch("app.services.real_saga.steps.storage_configuration.httpx.AsyncClient")
    async def test_reuses_when_exists(self, mock_client_cls):
        """Lookup retorna config com mesmo nome = reusa id sem POST."""
        step = StorageConfigurationStep()
        shared = SharedSagaState(workspace_root_bucket="my-root")
        ctx = _make_ctx(
            env_vars={
                "databricks_account_id": "acc-1",
                "databricks_oauth_client_id": "client-1",
                "databricks_oauth_secret": "secret-1",
                "project_name": "flowertex",
            },
            shared=shared,
        )

        client_mock = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = client_mock

        # Token + list (mesmo nome)
        token_resp = MagicMock()
        token_resp.json.return_value = {"access_token": "tok-1"}
        token_resp.raise_for_status = MagicMock()

        company_suffix = str(ctx.company_id).split("-")[0]
        existing_name = f"flowertex-{company_suffix}-storage"
        list_resp = MagicMock()
        list_resp.json.return_value = [
            {
                "storage_configuration_name": existing_name,
                "storage_configuration_id": "sc-existing-456",
            }
        ]
        list_resp.raise_for_status = MagicMock()

        client_mock.post.return_value = token_resp
        client_mock.get.return_value = list_resp

        await step.execute(ctx)

        assert ctx.shared.databricks_storage_config_id == "sc-existing-456"
        # POST so foi chamado pra OAuth, nao pra create
        assert client_mock.post.call_count == 1
