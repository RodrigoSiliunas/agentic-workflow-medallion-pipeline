"""Schemas de settings (request/response)."""

from pydantic import BaseModel


class CredentialSetRequest(BaseModel):
    credential_type: str
    value: str


class CredentialStatusResponse(BaseModel):
    credential_type: str
    is_configured: bool
    is_valid: bool
    last_tested_at: str | None = None


class TestCredentialResponse(BaseModel):
    success: bool
    message: str | None = None
    error: str | None = None


class CompanySettingsResponse(BaseModel):
    preferred_model: str
    preferred_provider: str = "anthropic"
    credentials: dict[str, dict]


class UpdatePreferredModelRequest(BaseModel):
    model: str  # ID literal aceito pelo provider (ex: "claude-opus-4-7")


class UpdatePreferredProviderRequest(BaseModel):
    provider: str  # "anthropic" | "openai" | "google"
