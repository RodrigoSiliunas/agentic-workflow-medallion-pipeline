"""Unit tests pra CustomLLMService — discovery models + encryption roundtrip."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.custom_llm_service import CustomLLMService


class TestDiscoverModels:
    @pytest.mark.asyncio
    @patch("app.core.url_validator.socket.getaddrinfo")
    @patch("app.services.custom_llm_service.httpx.AsyncClient")
    async def test_openai_endpoint_returns_models(self, mock_client_cls, mock_dns):
        """GET /v1/models retorna lista padrao OpenAI."""
        # SSRF guard resolve para IP publico — bypassa loopback/private check
        mock_dns.return_value = [(2, 1, 6, "", ("8.8.8.8", 0))]
        client_mock = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = client_mock

        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "data": [
                {"id": "qwen3.5:9b"},
                {"id": "gemma4:e2b"},
            ]
        }
        client_mock.get.return_value = resp

        success, models, server_type, error = await CustomLLMService.discover_models(
            "http://ollama:11434/v1", None
        )
        assert success is True
        assert server_type == "openai"
        assert error is None
        assert len(models) == 2
        assert models[0]["id"] == "qwen3.5:9b"

    @pytest.mark.asyncio
    @patch("app.core.url_validator.socket.getaddrinfo")
    @patch("app.services.custom_llm_service.httpx.AsyncClient")
    async def test_ollama_fallback_when_v1_fails(self, mock_client_cls, mock_dns):
        """v1/models 404 → fallback /api/tags."""
        mock_dns.return_value = [(2, 1, 6, "", ("8.8.8.8", 0))]
        client_mock = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = client_mock

        # /v1/models retorna 404
        resp_v1 = MagicMock()
        resp_v1.status_code = 404
        # /api/tags retorna OK
        resp_tags = MagicMock()
        resp_tags.status_code = 200
        resp_tags.json.return_value = {
            "models": [{"name": "qwen3.5:9b"}, {"name": "gemma4:e2b"}]
        }
        client_mock.get.side_effect = [resp_v1, resp_tags]

        success, models, server_type, _ = await CustomLLMService.discover_models(
            "http://ollama:11434/v1", None
        )
        assert success is True
        assert server_type == "ollama"
        assert len(models) == 2

    @pytest.mark.asyncio
    @patch("app.core.url_validator.socket.getaddrinfo")
    @patch("app.services.custom_llm_service.httpx.AsyncClient")
    async def test_both_fail_returns_error(self, mock_client_cls, mock_dns):
        """Ambos endpoints falham → success=False com error."""
        mock_dns.return_value = [(2, 1, 6, "", ("8.8.8.8", 0))]
        client_mock = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = client_mock

        resp_fail = MagicMock()
        resp_fail.status_code = 500
        client_mock.get.return_value = resp_fail

        success, models, server_type, error = await CustomLLMService.discover_models(
            "http://invalid:9999/v1", None
        )
        assert success is False
        assert error is not None
        assert models == []
        assert server_type is None

    @pytest.mark.asyncio
    @patch("app.core.url_validator.socket.getaddrinfo")
    @patch("app.services.custom_llm_service.httpx.AsyncClient")
    async def test_api_key_passes_authorization_header(self, mock_client_cls, mock_dns):
        """api_key vira Authorization: Bearer ..."""
        mock_dns.return_value = [(2, 1, 6, "", ("8.8.8.8", 0))]
        client_mock = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = client_mock

        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"data": [{"id": "gpt-4o"}]}
        client_mock.get.return_value = resp

        await CustomLLMService.discover_models(
            "https://openrouter.ai/api/v1", "sk-test-key"
        )
        call = client_mock.get.call_args
        assert call.kwargs["headers"]["Authorization"] == "Bearer sk-test-key"

    @pytest.mark.asyncio
    @patch("app.core.url_validator.socket.getaddrinfo")
    @patch("app.services.custom_llm_service.httpx.AsyncClient")
    async def test_network_error_is_handled(self, mock_client_cls, mock_dns):
        """httpx.HTTPError → suppressed, fallback tentado."""
        mock_dns.return_value = [(2, 1, 6, "", ("8.8.8.8", 0))]
        client_mock = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = client_mock

        client_mock.get.side_effect = httpx.ConnectError("connection refused")

        success, _, _, error = await CustomLLMService.discover_models(
            "http://nowhere:11434/v1", None
        )
        assert success is False
        assert error is not None
