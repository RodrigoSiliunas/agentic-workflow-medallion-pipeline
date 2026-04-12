"""Unit tests para schemas Pydantic novos."""


from app.schemas.deployment import (
    DeploymentConfigIn,
    DeploymentCreateRequest,
)
from app.schemas.template import TemplateResponse


def test_deployment_config_in_defaults():
    cfg = DeploymentConfigIn(name="my-deploy")
    assert cfg.environment == "prod"
    assert cfg.tags == {}
    assert cfg.credentials == {}
    assert cfg.env_vars == {}


def test_deployment_create_request_valida_slug():
    req = DeploymentCreateRequest(
        template_slug="pipeline-seguradora-whatsapp",
        config=DeploymentConfigIn(name="medallion-prod", environment="prod"),
    )
    assert req.template_slug == "pipeline-seguradora-whatsapp"
    assert req.config.environment == "prod"


def test_template_response_has_all_fields():
    fields = set(TemplateResponse.model_fields.keys())
    expected_subset = {
        "slug",
        "name",
        "tagline",
        "description",
        "category",
        "tags",
        "icon",
        "icon_bg",
        "version",
        "deploy_count",
        "env_schema",
        "changelog",
        "published",
    }
    assert expected_subset.issubset(fields)
