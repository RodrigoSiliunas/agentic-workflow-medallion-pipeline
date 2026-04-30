"""Tests para SSRF guards em app.core.url_validator."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from app.core.url_validator import (
    UnsafeURLError,
    validate_databricks_workspace_host,
    validate_public_url,
)


class TestValidateDatabricksHost:
    @pytest.mark.parametrize(
        "host",
        [
            "https://dbc-abc123.cloud.databricks.com",
            "https://dbc-abc123.cloud.databricks.com/",  # trailing slash
            "https://acme.azuredatabricks.net",
            "https://workspace.gcp.databricks.com",
            "https://staging.dev.databricks.com",
        ],
    )
    def test_valid_hosts_accepted(self, host: str):
        result = validate_databricks_workspace_host(host)
        # Trailing slash strip
        assert not result.endswith("/")
        # Scheme preservado
        assert result.startswith("https://")

    @pytest.mark.parametrize(
        "host",
        [
            "http://dbc-abc.cloud.databricks.com",  # http nao https
            "https://attacker.com",  # nao Databricks
            "https://databricks.com.attacker.net",  # subdomain hijack
            "https://dbc-abc.cloud.databricks.com.evil.com",
            "ftp://dbc-abc.cloud.databricks.com",
            "https://localhost:8080/cloud.databricks.com",
            "https://dbc-abc.cloud.databricks.com:8080",  # porta nao permitida
        ],
    )
    def test_invalid_hosts_rejected(self, host: str):
        with pytest.raises(UnsafeURLError):
            validate_databricks_workspace_host(host)

    def test_empty_string_rejected(self):
        with pytest.raises(UnsafeURLError, match="vazio"):
            validate_databricks_workspace_host("")

    def test_no_hostname_rejected(self):
        with pytest.raises(UnsafeURLError):
            validate_databricks_workspace_host("https://")


class TestValidatePublicUrl:
    def test_public_https_url_accepted(self):
        # Use api.openai.com — sempre publico
        result = validate_public_url("https://api.openai.com/v1")
        assert result == "https://api.openai.com/v1"

    @pytest.mark.parametrize(
        "url",
        [
            "ftp://example.com",
            "file:///etc/passwd",
            "javascript:alert(1)",
            "gopher://internal:70",
        ],
    )
    def test_non_http_schemes_rejected(self, url: str):
        with pytest.raises(UnsafeURLError):
            validate_public_url(url)

    def test_loopback_rejected_by_default(self):
        with pytest.raises(UnsafeURLError, match="loopback"):
            validate_public_url("http://127.0.0.1:8080")

    def test_loopback_allowed_when_flagged(self):
        result = validate_public_url(
            "http://127.0.0.1:8080", allow_loopback=True
        )
        assert "127.0.0.1" in result

    def test_localhost_loopback_allowed_when_flagged(self):
        # localhost → 127.0.0.1 ou ::1
        result = validate_public_url(
            "http://localhost:11434", allow_loopback=True
        )
        assert "localhost" in result

    def test_private_ip_rejected_via_dns_resolve(self):
        """Hostname publico que resolve pra IP privado e bloqueado."""
        with patch("app.core.url_validator.socket.getaddrinfo") as mock:
            # 10.0.0.1 = RFC1918 private
            mock.return_value = [(2, 1, 6, "", ("10.0.0.1", 0))]
            with pytest.raises(UnsafeURLError, match="privado"):
                validate_public_url("http://internal.corp:80")

    def test_link_local_metadata_rejected(self):
        """169.254.169.254 (cloud metadata) e bloqueado via link-local check."""
        with patch("app.core.url_validator.socket.getaddrinfo") as mock:
            mock.return_value = [(2, 1, 6, "", ("169.254.169.254", 0))]
            with pytest.raises(UnsafeURLError, match="link-local"):
                validate_public_url("http://metadata.aws:80")

    def test_unresolvable_host_rejected(self):
        with patch("app.core.url_validator.socket.getaddrinfo") as mock:
            import socket
            mock.side_effect = socket.gaierror("not found")
            with pytest.raises(UnsafeURLError, match="nao resolve"):
                validate_public_url("http://nonexistent.invalid")

    def test_unusual_port_rejected(self):
        with pytest.raises(UnsafeURLError, match="porta nao permitida"):
            validate_public_url("http://example.com:31337")

    def test_ollama_default_port_allowed(self):
        """Porta 11434 (Ollama) e whitelistada pra dev local."""
        # Ate sem allow_loopback, IP publico em :11434 passa
        with patch("app.core.url_validator.socket.getaddrinfo") as mock:
            mock.return_value = [(2, 1, 6, "", ("8.8.8.8", 0))]
            result = validate_public_url("http://example.com:11434")
            assert ":11434" in result
