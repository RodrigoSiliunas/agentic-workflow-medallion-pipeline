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
    # `catalog_name` do wizard e honrado e mapeado pra `catalog` (chave que o
    # saga e o editor leem); o input explicito vence o default de environment
    # isolation (que poria `medallion_dev` em ambiente dev).
    assert body["config"]["env_vars"]["catalog"] == "test"

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


async def test_create_deployment_invalid_catalog_fails_fast_422(
    http_client: httpx.AsyncClient, auth_headers: dict, db_session
):
    """Catalog com hifen (invalido no Unity Catalog) deve falhar NO SUBMIT
    (422), nao 10 steps depois no saga — bug real visto no E2E com
    'medallion-security'."""
    await seed_templates(db_session)

    response = await http_client.post(
        "/api/v1/deployments",
        json={
            "template_slug": "pipeline-seguradora-whatsapp",
            "config": {
                "name": "deploy-catalogo-invalido",
                "environment": "prod",
                "tags": {},
                "credentials": {},
                "env_vars": {"catalog_name": "medallion-security"},
            },
        },
        headers=auth_headers,
    )
    assert response.status_code == 422, response.text
    assert "medallion-security" in response.json()["detail"]

    # Nenhum deployment deve ter sido criado
    listing = await http_client.get("/api/v1/deployments", headers=auth_headers)
    assert listing.json() == []


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
