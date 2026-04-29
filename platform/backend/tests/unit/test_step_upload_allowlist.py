"""Unit tests para upload._is_pipeline_path — allowlist de paths sincronizados."""

import pytest

from app.services.real_saga.steps.upload import _is_pipeline_path


@pytest.mark.parametrize("path", [
    "pipelines/seguradora/notebooks/bronze/ingest.py",
    "pipelines/whatsapp/notebooks/silver/dedup.py",
    "pipelines/whatsapp/pipeline_lib/storage/s3_client.py",
    "pipelines/whatsapp/config/gold_phases.yaml",
    "observer-framework/notebooks/collect_and_fix.py",
    "observer-framework/observer/config.py",
])
def test_allowed_paths_included(path: str):
    assert _is_pipeline_path(path) is True


@pytest.mark.parametrize("path", [
    # Fora do allowlist
    "README.md",
    "docs/architecture.md",
    "platform/backend/app/main.py",
    ".github/workflows/ci.yml",
    "infra/aws/terraform.tfvars",
    "scripts/setup.sh",
    # Extensoes nao suportadas
    "pipelines/foo/notebooks/data.parquet",
    "pipelines/foo/notebooks/img.png",
    # Tests sao excluidos
    "pipelines/foo/tests/test_x.py",
    "observer-framework/tests/test_validator.py",
])
def test_denied_paths_excluded(path: str):
    assert _is_pipeline_path(path) is False


def test_yaml_only_under_pipelines_config():
    """yaml so passa em pipelines/*/config/. Em outros paths nao."""
    assert _is_pipeline_path("pipelines/x/config/foo.yaml") is True
    assert _is_pipeline_path("observer-framework/observer/foo.yaml") is True
    # YAML solto fora de allowlist nao passa
    assert _is_pipeline_path("docs/foo.yaml") is False
