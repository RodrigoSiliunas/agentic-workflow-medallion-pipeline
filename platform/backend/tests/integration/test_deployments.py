"""Integration tests — deployments CRUD (saga nao e executada)."""

import httpx
import pytest

from app.database.seed import seed_templates

pytestmark = pytest.mark.asyncio


async def test_list_deployments_empty(
    http_client: httpx.AsyncClient, auth_headers: dict
):
    response = await http_client.get("/api/v1/deployments", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


async def test_create_deployment_with_seeded_template(
    http_client: httpx.AsyncClient, auth_headers: dict, db_session
):
    await seed_templates(db_session)

    payload = {
        "template_slug": "pipeline-seguradora-whatsapp",
        "config": {
            "name": "integration-test-deploy",
            "environment": "dev",
            "tags": {"source": "pytest"},
            "credentials": {
                "aws_access_key_id": "AKIAFAKE",
                "aws_secret_access_key": "secret",
            },
            "env_vars": {"catalog_name": "test"},
        },
    }
    response = await http_client.post(
        "/api/v1/deployments",
        json=payload,
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "integration-test-deploy"
    assert body["environment"] == "dev"
    assert body["template_slug"] == "pipeline-seguradora-whatsapp"
    # credenciais nao podem voltar em plaintext
    assert body["config"]["credentials"]["aws_access_key_id"] == "***"

    deployment_id = body["id"]

    # GET by id
    detail = await http_client.get(
        f"/api/v1/deployments/{deployment_id}", headers=auth_headers
    )
    assert detail.status_code == 200

    # Lista agora tem 1
    listing = await http_client.get("/api/v1/deployments", headers=auth_headers)
    assert listing.status_code == 200
    assert len(listing.json()) == 1


async def test_create_deployment_unknown_template_404(
    http_client: httpx.AsyncClient, auth_headers: dict
):
    response = await http_client.post(
        "/api/v1/deployments",
        json={
            "template_slug": "does-not-exist",
            "config": {
                "name": "x",
                "environment": "dev",
                "tags": {},
                "credentials": {},
                "env_vars": {},
            },
        },
        headers=auth_headers,
    )
    assert response.status_code == 404
