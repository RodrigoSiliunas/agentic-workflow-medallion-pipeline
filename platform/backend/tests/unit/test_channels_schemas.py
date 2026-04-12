"""Unit tests para schemas Pydantic de channels."""

import pytest
from pydantic import ValidationError

from app.schemas.channel import (
    ConnectChannelRequest,
    CreateChannelRequest,
    OmniInstanceResponse,
    QRCodeResponse,
)


def test_create_channel_request_whatsapp():
    req = CreateChannelRequest(name="acme-suporte", channel="whatsapp")
    assert req.channel == "whatsapp"
    assert req.name == "acme-suporte"


def test_create_channel_request_rejects_invalid_channel():
    with pytest.raises(ValidationError):
        CreateChannelRequest(name="test", channel="slack")  # type: ignore[arg-type]


def test_create_channel_request_nome_minimo():
    with pytest.raises(ValidationError):
        CreateChannelRequest(name="a", channel="discord")


def test_connect_channel_request_token_opcional():
    req = ConnectChannelRequest()
    assert req.token is None

    req2 = ConnectChannelRequest(token="bot-token-123")
    assert req2.token == "bot-token-123"


def test_omni_instance_response_fields():
    fields = set(OmniInstanceResponse.model_fields.keys())
    expected = {
        "id",
        "omni_instance_id",
        "name",
        "channel",
        "state",
        "last_sync_at",
        "last_error",
        "created_at",
        "updated_at",
    }
    assert expected.issubset(fields)


def test_qrcode_response_minimal():
    resp = QRCodeResponse(instance_id="abc", state="connecting")
    assert resp.qr_code is None
    assert resp.expires_at is None
