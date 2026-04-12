"""Unit tests para ValidateStep com boto3 + httpx mockados."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.real_saga.base import (
    CredentialMissingError,
    DeploymentCredentials,
    SharedSagaState,
    StepContext,
)
from app.services.real_saga.steps.validate import ValidateStep


def _make_ctx(
    credentials: DeploymentCredentials | None = None,
) -> StepContext:
    """Cria um StepContext minimo para testes do ValidateStep."""
    dep = MagicMock()
    dep.id = uuid.uuid4()
    dep.company_id = uuid.uuid4()
    dep.config = {}
    return StepContext(
        deployment=dep,
        step_id="validate",
        step_name="Validate Credentials",
        credentials=credentials or DeploymentCredentials(),
        emit_log=AsyncMock(),
        state_dir=MagicMock(),
        shared=SharedSagaState(),
    )


class TestCheckAws:
    @patch("app.services.real_saga.steps.validate.boto3_session")
    async def test_check_aws_succeeds_with_valid_sts(self, mock_boto3_session):
        """STS GetCallerIdentity retornando account info deve logar sucesso."""
        mock_session = MagicMock()
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {
            "Account": "123456789012",
            "Arn": "arn:aws:iam::123456789012:user/test",
        }
        mock_session.client.return_value = mock_sts
        mock_boto3_session.return_value = mock_session

        creds = DeploymentCredentials(
            aws_access_key_id="AKIAEXAMPLE",
            aws_secret_access_key="secret",
            aws_region="us-east-2",
        )
        ctx = _make_ctx(credentials=creds)

        # Deve executar sem exception
        await ValidateStep._check_aws(ctx)

        # Verifica que logou info com a account
        info_calls = [
            call.args[1]
            for call in ctx.emit_log.call_args_list
            if call.args[0] == "info"
        ]
        assert any("123456789012" in msg for msg in info_calls)

    @patch("app.services.real_saga.steps.validate.boto3_session")
    async def test_check_aws_raises_on_missing_credentials(self, mock_boto3_session):
        """Credenciais AWS vazias devem levantar CredentialMissingError."""
        mock_boto3_session.side_effect = CredentialMissingError(
            "Credencial obrigatoria nao configurada: aws_access_key_id"
        )
        ctx = _make_ctx(credentials=DeploymentCredentials())

        with pytest.raises(CredentialMissingError, match="aws_access_key_id"):
            await ValidateStep._check_aws(ctx)


class TestCheckAnthropic:
    async def test_check_anthropic_warns_when_key_missing(self):
        """Sem anthropic_api_key deve emitir warning, sem exception."""
        ctx = _make_ctx(credentials=DeploymentCredentials())

        await ValidateStep._check_anthropic(ctx)

        # Deve ter emitido um warning via emit_log
        warn_calls = [
            call.args[1]
            for call in ctx.emit_log.call_args_list
            if call.args[0] == "warn"
        ]
        assert any("Anthropic" in msg for msg in warn_calls)


class TestCheckGithub:
    async def test_check_github_warns_when_token_missing(self):
        """Sem github_token deve emitir warning, sem exception."""
        ctx = _make_ctx(credentials=DeploymentCredentials())

        await ValidateStep._check_github(ctx)

        # Deve ter emitido um warning via emit_log
        warn_calls = [
            call.args[1]
            for call in ctx.emit_log.call_args_list
            if call.args[0] == "warn"
        ]
        assert any("GitHub" in msg for msg in warn_calls)
