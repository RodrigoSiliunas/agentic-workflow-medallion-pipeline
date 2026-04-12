"""Integration tests — channels (Omni indisponivel no teste, state=failed)."""

import httpx
import pytest

pytestmark = pytest.mark.asyncio


async def test_list_channels_empty(
    http_client: httpx.AsyncClient, auth_headers: dict
):
    response = await http_client.get("/api/v1/channels", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


async def test_create_channel_fails_gracefully_without_omni(
    http_client: httpx.AsyncClient, auth_headers: dict
):
    """Omni gateway nao esta rodando no teste — instance deve ir pra state=failed."""
    response = await http_client.post(
        "/api/v1/channels",
        json={"name": "test-suporte", "channel": "whatsapp"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "test-suporte"
    assert body["channel"] == "whatsapp"
    assert body["state"] == "failed"
    assert body["last_error"] is not None


async def test_create_channel_invalid_kind_rejected(
    http_client: httpx.AsyncClient, auth_headers: dict
):
    response = await http_client.post(
        "/api/v1/channels",
        json={"name": "test", "channel": "slack"},
        headers=auth_headers,
    )
    assert response.status_code == 422
