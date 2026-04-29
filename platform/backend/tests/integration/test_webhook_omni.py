"""Integration tests — webhook /api/v1/webhooks/omni HMAC + tenant isolation."""

import hashlib
import hmac
import json

import httpx
import pytest

from app.core.config import settings

pytestmark = pytest.mark.asyncio


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


async def test_rejects_missing_signature(http_client: httpx.AsyncClient):
    """Sem header X-Webhook-Signature -> 401."""
    response = await http_client.post(
        "/api/v1/webhooks/omni",
        content=b'{"type":"message"}',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 401


async def test_rejects_invalid_signature(http_client: httpx.AsyncClient):
    """X-Webhook-Signature errado -> 401."""
    settings.OMNI_WEBHOOK_SECRET = "test-secret"
    body = b'{"type":"message"}'
    response = await http_client.post(
        "/api/v1/webhooks/omni",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Signature": "wrong-sig",
        },
    )
    assert response.status_code == 401


async def test_returns_503_when_secret_unset(http_client: httpx.AsyncClient):
    """OMNI_WEBHOOK_SECRET vazio -> 503 (nao falha aberto)."""
    original = settings.OMNI_WEBHOOK_SECRET
    settings.OMNI_WEBHOOK_SECRET = ""
    try:
        response = await http_client.post(
            "/api/v1/webhooks/omni",
            content=b"{}",
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": "any",
            },
        )
        assert response.status_code == 503
    finally:
        settings.OMNI_WEBHOOK_SECRET = original


async def test_unknown_instance_rejected(http_client: httpx.AsyncClient):
    """instanceId nao registrado em OmniInstance -> ignored (nao propaga)."""
    settings.OMNI_WEBHOOK_SECRET = "test-secret"
    body = json.dumps({
        "type": "message",
        "from": "5511999999999@s.whatsapp.net",
        "instanceId": "unknown-instance-id",
        "content": {"text": "ola"},
    }).encode()
    sig = _sign(body, "test-secret")
    response = await http_client.post(
        "/api/v1/webhooks/omni",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Signature": sig,
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
