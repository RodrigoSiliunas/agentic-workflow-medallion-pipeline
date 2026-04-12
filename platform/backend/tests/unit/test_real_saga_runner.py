"""Unit tests para RealSagaRunner."""

import contextlib
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.real_saga.base import DeploymentCredentials, SharedSagaState
from app.services.real_saga.runner import RealSagaRunner, _state_dir_for


def _make_deployment(
    company_id: uuid.UUID | None = None,
    deployment_id: uuid.UUID | None = None,
    environment: str = "prod",
) -> MagicMock:
    """Cria um mock de Deployment com campos essenciais."""
    dep = MagicMock()
    dep.id = deployment_id or uuid.uuid4()
    dep.company_id = company_id or uuid.uuid4()
    dep.environment = environment
    dep.config = {}
    return dep


class TestRealSagaRunnerExecuteStep:
    async def test_execute_step_raises_on_unknown_step_id(self):
        runner = RealSagaRunner()
        creds = DeploymentCredentials(
            aws_access_key_id="ak",
            aws_secret_access_key="sk",
            aws_region="us-east-2",
        )
        with pytest.raises(ValueError, match="step_id desconhecido"):
            await runner.execute_step(
                deployment=_make_deployment(),
                step_id="nonexistent",
                step_name="Nonexistent Step",
                emit_log=AsyncMock(),
                credentials=creds,
            )

    async def test_execute_step_raises_without_credentials(self):
        runner = RealSagaRunner()
        with pytest.raises(ValueError, match="credentials"):
            await runner.execute_step(
                deployment=_make_deployment(),
                step_id="validate",
                step_name="Validate",
                emit_log=AsyncMock(),
                credentials=None,
            )


class TestCleanupSharedState:
    def test_cleanup_shared_state_removes_entry(self):
        runner = RealSagaRunner()
        dep_id = str(uuid.uuid4())
        # Insere shared state manualmente
        runner._shared_per_deployment[dep_id] = SharedSagaState(s3_bucket="test-bucket")
        assert dep_id in runner._shared_per_deployment

        runner.cleanup_shared_state(dep_id)
        assert dep_id not in runner._shared_per_deployment

    def test_cleanup_shared_state_noop_for_missing(self):
        runner = RealSagaRunner()
        # Nao deve levantar exception
        runner.cleanup_shared_state("does-not-exist")


class TestStateDirFor:
    def test_state_dir_uses_company_id(self):
        company_id = uuid.uuid4()
        dep = _make_deployment(company_id=company_id)

        result = _state_dir_for(dep)

        # O path final deve conter o company_id
        assert str(company_id) in str(result)

    def test_state_dir_uses_custom_base_when_configured(self, tmp_path):
        from pathlib import Path

        from app.core.config import settings

        custom_base = str(tmp_path / "custom_saga")
        company_id = uuid.uuid4()
        dep = _make_deployment(company_id=company_id)

        # settings e Pydantic Settings — usa object.__setattr__ pra injetar o atributo
        original = getattr(settings, "REAL_SAGA_DATA_DIR", None)
        try:
            object.__setattr__(settings, "REAL_SAGA_DATA_DIR", custom_base)
            result = _state_dir_for(dep)
            # O path deve comecar com o custom base (independente do OS)
            assert result.parent == Path(custom_base)
            assert str(company_id) in str(result)
        finally:
            if original is None:
                with contextlib.suppress(AttributeError):
                    object.__delattr__(settings, "REAL_SAGA_DATA_DIR")
            else:
                object.__setattr__(settings, "REAL_SAGA_DATA_DIR", original)

    def test_state_dir_defaults_to_data_real_saga(self, monkeypatch):
        from app.core.config import settings

        # Garante que o atributo nao esta configurado
        if hasattr(settings, "REAL_SAGA_DATA_DIR"):
            monkeypatch.setattr(settings, "REAL_SAGA_DATA_DIR", None)

        dep = _make_deployment()
        result = _state_dir_for(dep)

        assert "real_saga" in str(result)
