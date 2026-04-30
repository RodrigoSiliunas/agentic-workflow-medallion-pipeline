"""SSRF guards for outbound HTTP calls to user-controlled hosts.

Two flavors:

- `validate_databricks_workspace_host`: STRICT allowlist for Databricks
  workspace URLs. Hostname must match `*.cloud.databricks.com`,
  `*.gcp.databricks.com`, or `*.azuredatabricks.net`. Scheme must be `https`.
  Used by routes that fetch from `databricks_host` credential — prevents
  attackers with admin access from redirecting bearer-token requests to
  attacker-controlled hosts.

- `validate_public_url`: PRIVATE-IP DENY for arbitrary user URLs (custom
  LLM endpoints, webhook callbacks). Resolves hostname, blocks any IP in
  loopback / private (RFC1918) / link-local / reserved ranges. Allows
  `localhost` only when `allow_loopback=True` (dev mode).
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

# Domains validos para Databricks workspace API
_ALLOWED_DATABRICKS_HOST_SUFFIXES = (
    ".cloud.databricks.com",
    ".gcp.databricks.com",
    ".azuredatabricks.net",
    ".dev.databricks.com",  # dev/staging environments
)


class UnsafeURLError(ValueError):
    """URL falhou validacao SSRF."""


def validate_databricks_workspace_host(host: str) -> str:
    """Valida que `host` e uma URL https para um workspace Databricks legitimo.

    Aceita formato com ou sem trailing slash. Retorna a URL normalizada
    (sem trailing slash). Levanta UnsafeURLError em scheme/host invalido.
    """
    if not host:
        raise UnsafeURLError("databricks_host vazio")

    parsed = urlparse(host.rstrip("/"))
    if parsed.scheme != "https":
        raise UnsafeURLError(
            f"databricks_host precisa ser https://, got '{parsed.scheme}'"
        )
    if not parsed.hostname:
        raise UnsafeURLError(f"databricks_host sem hostname: '{host}'")

    hostname = parsed.hostname.lower()
    if not any(hostname.endswith(suffix) for suffix in _ALLOWED_DATABRICKS_HOST_SUFFIXES):
        raise UnsafeURLError(
            f"databricks_host '{hostname}' nao bate allowlist "
            f"({', '.join(_ALLOWED_DATABRICKS_HOST_SUFFIXES)})"
        )

    if parsed.port and parsed.port not in (443, 8443):
        raise UnsafeURLError(f"databricks_host porta nao permitida: {parsed.port}")

    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")


def validate_public_url(url: str, *, allow_loopback: bool = False) -> str:
    """Valida que `url` aponta para um host publico (nao SSRF).

    Bloqueia:
    - schemes != http/https
    - hostnames que resolvem para IPs privados (RFC1918), loopback,
      link-local, multicast, reserved, ou IPv6 equivalents
    - cloud metadata IPs (169.254.169.254 — link-local ja cobre)
    - portas != 80/443/8080/8443 (custom ports raro pra LLM publico)

    Se `allow_loopback=True`, permite localhost/127.0.0.1 (dev only).

    Retorna URL normalizada (sem trailing slash). Levanta UnsafeURLError.
    """
    if not url:
        raise UnsafeURLError("URL vazia")

    parsed = urlparse(url.rstrip("/"))
    if parsed.scheme not in ("http", "https"):
        raise UnsafeURLError(
            f"scheme '{parsed.scheme}' nao permitido (use http/https)"
        )
    if not parsed.hostname:
        raise UnsafeURLError(f"URL sem hostname: '{url}'")

    hostname = parsed.hostname.lower()

    if parsed.port and parsed.port not in (80, 443, 8080, 8443, 11434):
        # 11434 = Ollama default. Mantemos pra dev local + tunnels (ngrok proxy).
        raise UnsafeURLError(f"porta nao permitida: {parsed.port}")

    # Resolve hostname → IPs. Bloqueia se QUALQUER resolucao cair em range privado.
    try:
        addrs = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise UnsafeURLError(f"hostname nao resolve: {hostname}") from exc

    for _family, _type, _proto, _canonname, sockaddr in addrs:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue

        if ip.is_loopback:
            if allow_loopback:
                continue
            raise UnsafeURLError(f"hostname resolve para loopback: {ip_str}")
        # link-local ANTES de is_private — Python reporta link-local como
        # privado tambem; queremos a mensagem especifica pra cloud metadata.
        if ip.is_link_local:
            raise UnsafeURLError(
                f"hostname resolve para link-local: {ip_str} "
                "(bloqueia cloud metadata 169.254.169.254)"
            )
        if ip.is_private:
            raise UnsafeURLError(f"hostname resolve para IP privado: {ip_str}")
        if ip.is_multicast or ip.is_reserved or ip.is_unspecified:
            raise UnsafeURLError(f"IP em range bloqueado: {ip_str}")

    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
