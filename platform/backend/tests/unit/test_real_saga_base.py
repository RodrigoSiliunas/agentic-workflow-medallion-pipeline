"""Unit tests para DeploymentCredentials e SharedSagaState."""

import pytest

from app.services.real_saga.base import (
    CredentialMissingError,
    DeploymentCredentials,
    SharedSagaState,
)


class TestDeploymentCredentials:
    def test_require_returns_value_when_set(self):
        creds = DeploymentCredentials(aws_access_key_id="AKIAEXAMPLE123456")
        assert creds.require("aws_access_key_id") == "AKIAEXAMPLE123456"

    def test_require_raises_credential_missing_when_none(self):
        creds = DeploymentCredentials()
        with pytest.raises(CredentialMissingError, match="aws_access_key_id"):
            creds.require("aws_access_key_id")

    def test_require_raises_credential_missing_when_empty_string(self):
        creds = DeploymentCredentials(aws_access_key_id="")
        with pytest.raises(CredentialMissingError):
            creds.require("aws_access_key_id")

    def test_to_env_only_includes_set_values(self):
        creds = DeploymentCredentials(aws_access_key_id="key123", aws_region="us-east-2")
        env = creds.to_env()
        # Somente campos setados aparecem
        assert "AWS_ACCESS_KEY_ID" in env
        assert "AWS_REGION" in env
        # Campos None nao aparecem
        assert "AWS_SECRET_ACCESS_KEY" not in env
        assert "DATABRICKS_HOST" not in env
        assert "GITHUB_TOKEN" not in env
        assert "ANTHROPIC_API_KEY" not in env

    def test_to_env_maps_correct_key_names(self):
        creds = DeploymentCredentials(
            aws_access_key_id="ak",
            aws_secret_access_key="sk",
            aws_region="us-east-2",
            databricks_host="https://dbc-xxx.cloud.databricks.com",
            databricks_token="dapiABC",
            github_token="ghp_xxx",
            github_repo="org/repo",
            anthropic_api_key="sk-ant-xxx",
        )
        env = creds.to_env()
        assert env["AWS_ACCESS_KEY_ID"] == "ak"
        assert env["AWS_SECRET_ACCESS_KEY"] == "sk"
        assert env["AWS_REGION"] == "us-east-2"
        assert env["AWS_DEFAULT_REGION"] == "us-east-2"
        assert env["DATABRICKS_HOST"] == "https://dbc-xxx.cloud.databricks.com"
        assert env["DATABRICKS_TOKEN"] == "dapiABC"
        assert env["GITHUB_TOKEN"] == "ghp_xxx"
        assert env["GITHUB_REPO"] == "org/repo"
        assert env["ANTHROPIC_API_KEY"] == "sk-ant-xxx"

    def test_to_env_empty_when_all_none(self):
        creds = DeploymentCredentials()
        assert creds.to_env() == {}


class TestSharedSagaState:
    def test_shared_state_defaults_all_none(self):
        state = SharedSagaState()
        assert state.s3_bucket is None
        assert state.s3_bucket_url is None
        assert state.databricks_role_arn is None
        assert state.secret_scope is None
        assert state.catalog is None
        assert state.repo_path is None
        assert state.observer_job_id is None
        assert state.workflow_job_id is None
        assert state.run_id is None
