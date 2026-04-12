"""Unit tests para o seed de templates (valida shape dos dados)."""

import pytest

from app.database.seed import TEMPLATE_SEEDS


def test_three_templates_defined():
    assert len(TEMPLATE_SEEDS) == 3
    slugs = {t["slug"] for t in TEMPLATE_SEEDS}
    assert slugs == {
        "pipeline-seguradora-whatsapp",
        "pipeline-crm-sap",
        "pipeline-ecommerce-hotmart",
    }


REQUIRED_KEYS = {
    "slug",
    "name",
    "tagline",
    "description",
    "category",
    "tags",
    "icon",
    "icon_bg",
    "version",
    "author",
    "deploy_count",
    "duration_estimate",
    "architecture_bullets",
    "env_schema",
    "changelog",
    "published",
}


@pytest.mark.parametrize("template", TEMPLATE_SEEDS, ids=lambda t: t["slug"])
def test_template_has_required_fields(template):
    missing = REQUIRED_KEYS - set(template.keys())
    assert not missing, f"{template['slug']} faltando {missing}"
    assert template["published"] is True
    assert isinstance(template["tags"], list) and len(template["tags"]) > 0
    assert isinstance(template["architecture_bullets"], list)
    assert isinstance(template["env_schema"], list)
    assert isinstance(template["changelog"], list) and len(template["changelog"]) >= 1


@pytest.mark.parametrize("template", TEMPLATE_SEEDS, ids=lambda t: t["slug"])
def test_env_schema_entries_valid(template):
    for entry in template["env_schema"]:
        assert "key" in entry
        assert "label" in entry
        assert "type" in entry
        assert "required" in entry
        assert isinstance(entry["required"], bool)


@pytest.mark.parametrize("template", TEMPLATE_SEEDS, ids=lambda t: t["slug"])
def test_changelog_entries_valid(template):
    for entry in template["changelog"]:
        assert "version" in entry
        assert "date" in entry
        assert "changes" in entry
        assert isinstance(entry["changes"], list)
        assert len(entry["changes"]) >= 1
