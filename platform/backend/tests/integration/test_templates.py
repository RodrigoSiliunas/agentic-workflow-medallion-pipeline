"""Integration tests — templates endpoint + seed."""

import httpx
import pytest

from app.database.seed import seed_templates

pytestmark = pytest.mark.asyncio


async def test_list_templates_empty_without_seed(
    http_client: httpx.AsyncClient, auth_headers: dict
):
    response = await http_client.get("/api/v1/templates", headers=auth_headers)
    assert response.status_code == 200
    # Sem seed, lista pode estar vazia
    assert isinstance(response.json(), list)


async def test_list_templates_after_seed(
    http_client: httpx.AsyncClient, auth_headers: dict, db_session
):
    inserted = await seed_templates(db_session)
    assert inserted >= 1

    response = await http_client.get("/api/v1/templates", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    slugs = {t["slug"] for t in data}
    assert "pipeline-seguradora-whatsapp" in slugs


async def test_get_template_by_slug(
    http_client: httpx.AsyncClient, auth_headers: dict, db_session
):
    await seed_templates(db_session)
    response = await http_client.get(
        "/api/v1/templates/pipeline-seguradora-whatsapp",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Pipeline Seguradora WhatsApp"
    assert len(data["env_schema"]) >= 2


async def test_get_template_404(http_client: httpx.AsyncClient, auth_headers: dict):
    response = await http_client.get(
        "/api/v1/templates/nonexistent", headers=auth_headers
    )
    assert response.status_code == 404
