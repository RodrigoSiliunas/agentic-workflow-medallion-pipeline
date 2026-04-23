"""Pydantic schemas para channels (Omni instances)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ChannelKind = Literal["whatsapp", "discord", "telegram"]
OmniInstanceState = Literal["connecting", "connected", "disconnected", "failed"]


class CreateChannelRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    channel: ChannelKind


class ConnectChannelRequest(BaseModel):
    token: str | None = Field(None, description="Token Discord/Telegram")


class OmniInstanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    omni_instance_id: str | None
    name: str
    channel: ChannelKind
    state: OmniInstanceState
    last_sync_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime
    preferred_provider: str | None = None
    preferred_model: str | None = None


class UpdateChannelLLMRequest(BaseModel):
    """PATCH endpoint pra trocar LLM provider/model do canal."""

    provider: str | None = None  # vazio limpa override (volta default empresa)
    model: str | None = None


class QRCodeResponse(BaseModel):
    """Resposta do GET /channels/{id}/qr para WhatsApp pairing."""

    instance_id: str
    state: OmniInstanceState
    qr_code: str | None = Field(None, description="Base64 data URL ou texto")
    expires_at: datetime | None = None
