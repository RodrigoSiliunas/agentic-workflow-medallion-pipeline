"""Schemas pra custom LLM endpoints (Ollama, vLLM, OpenRouter, etc)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CustomLLMModelInfo(BaseModel):
    id: str
    label: str | None = None


class CustomLLMEndpointCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    base_url: str = Field(..., min_length=8, max_length=500)
    api_key: str | None = None  # Opcional (Ollama nao exige)
    models: list[CustomLLMModelInfo] = Field(default_factory=list)
    enabled: bool = True


class CustomLLMEndpointUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=100)
    base_url: str | None = Field(None, min_length=8, max_length=500)
    api_key: str | None = None  # vazio = manter atual; "" string limpa
    models: list[CustomLLMModelInfo] | None = None
    enabled: bool | None = None


class CustomLLMEndpointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    base_url: str
    has_api_key: bool  # nao retorna a key, so flag
    models: list[CustomLLMModelInfo] = Field(default_factory=list)
    enabled: bool
    last_tested_at: datetime | None
    last_test_status: str | None
    created_at: datetime
    updated_at: datetime


class TestEndpointRequest(BaseModel):
    """Test connection — usado tanto pra novo (body completo) quanto edit."""

    base_url: str
    api_key: str | None = None


class TestEndpointResponse(BaseModel):
    success: bool
    error: str | None = None
    discovered_models: list[CustomLLMModelInfo] = Field(default_factory=list)
    server_type: str | None = None  # "ollama" | "openai" | "vllm" | "unknown"
