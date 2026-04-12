"""Integration tests — auth + users/me + seed pipeline."""

import httpx
import pytest

pytestmark = pytest.mark.asyncio


async def test_register_creates_company_user_and_default_pipeline(
    http_client: httpx.AsyncClient,
):
    response = await http_client.post(
        "/api/v1/auth/register-company",
        json={
            "company_name": "Acme Inc",
            "company_slug": "acme-inc-test",
            "admin_name": "Alice",
            "admin_email": "alice@example.com",
            "admin_password": "test1234",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body

    # Login com a conta recem criada deve funcionar
    login = await http_client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "test1234"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    # /users/me retorna o perfil completo
    me = await http_client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me.status_code == 200
    profile = me.json()
    assert profile["email"] == "alice@example.com"
    assert profile["name"] == "Alice"
    assert profile["role"] == "root"

    # Um pipeline default deve ter sido criado durante o register
    pipelines = await http_client.get(
        "/api/v1/pipelines",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert pipelines.status_code == 200
    data = pipelines.json()
    assert len(data) >= 1
    assert any("primeiro" in p["name"].lower() for p in data)


async def test_login_with_wrong_password_returns_401(
    http_client: httpx.AsyncClient, registered_company: dict
):
    response = await http_client.post(
        "/api/v1/auth/login",
        json={"email": registered_company["email"], "password": "wrongpass1234"},
    )
    assert response.status_code == 401


async def test_duplicate_company_slug_rejected(http_client: httpx.AsyncClient):
    payload = {
        "company_name": "First",
        "company_slug": "duplicate-slug",
        "admin_name": "Admin Test",
        "admin_email": "a@example.com",
        "admin_password": "test1234secure",
    }
    r1 = await http_client.post("/api/v1/auth/register-company", json=payload)
    assert r1.status_code == 201

    payload["admin_email"] = "b@example.com"
    r2 = await http_client.post("/api/v1/auth/register-company", json=payload)
    assert r2.status_code == 409
