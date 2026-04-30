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


async def test_email_squat_protection_allows_same_email_in_different_company(
    http_client: httpx.AsyncClient,
):
    """Atacante NAO bloqueia mais empresa B de cadastrar mesmo email
    so porque squatou na empresa A. Email unique por (company_id, email)."""
    # Empresa A registra email victim@example.com
    r1 = await http_client.post(
        "/api/v1/auth/register-company",
        json={
            "company_name": "Squatter",
            "company_slug": "squatter-co",
            "admin_name": "Bad Actor",
            "admin_email": "victim@example.com",
            "admin_password": "squatpass123",
        },
    )
    assert r1.status_code == 201

    # Empresa B (legitimo dono do email) consegue registrar com mesmo email
    r2 = await http_client.post(
        "/api/v1/auth/register-company",
        json={
            "company_name": "Victim Real",
            "company_slug": "victim-real",
            "admin_name": "Real Owner",
            "admin_email": "victim@example.com",
            "admin_password": "realpass1234",
        },
    )
    assert r2.status_code == 201, f"Squat: {r2.text}"


async def test_login_requires_company_slug_when_email_collides(
    http_client: httpx.AsyncClient,
):
    """Email cadastrado em 2 empresas — login sem company_slug retorna 409."""
    for slug, password in (
        ("collide-a", "passworda1234"),
        ("collide-b", "passwordb1234"),
    ):
        r = await http_client.post(
            "/api/v1/auth/register-company",
            json={
                "company_name": f"C-{slug}",
                "company_slug": slug,
                "admin_name": "Owner",
                "admin_email": "shared@example.com",
                "admin_password": password,
            },
        )
        assert r.status_code == 201

    # Login sem slug → 409 (ambiguo)
    ambig = await http_client.post(
        "/api/v1/auth/login",
        json={"email": "shared@example.com", "password": "passworda1234"},
    )
    assert ambig.status_code == 409

    # Login com slug correto → 200
    ok = await http_client.post(
        "/api/v1/auth/login",
        json={
            "email": "shared@example.com",
            "password": "passworda1234",
            "company_slug": "collide-a",
        },
    )
    assert ok.status_code == 200

    # Login com slug correto + senha errada → 401
    wrong_pwd = await http_client.post(
        "/api/v1/auth/login",
        json={
            "email": "shared@example.com",
            "password": "passwordb1234",  # senha de B, mas slug A
            "company_slug": "collide-a",
        },
    )
    assert wrong_pwd.status_code == 401
