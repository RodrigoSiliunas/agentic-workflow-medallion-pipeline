"""Security headers middleware (T2 Phase 3).

Adiciona Content-Security-Policy, Strict-Transport-Security e
Permissions-Policy em toda resposta. Complementa X-Content-Type-Options,
X-Frame-Options e Referrer-Policy já adicionados em `main.security_headers`.

Uso:
    from app.middleware.security_headers import SecurityHeadersMiddleware

    app.add_middleware(SecurityHeadersMiddleware, enable_hsts=True)

Config:
- `SECURITY_HEADERS_CSP` — sobrescreve a CSP default (env var).
- `SECURITY_HEADERS_HSTS` — liga/desliga HSTS (default on).
- Em dev, CSP permite `ws://` para HMR do Nuxt e `localhost` origins.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

# Default CSP — tight para prod. Dev herda via config (vide __init__).
DEFAULT_CSP_PROD = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: https:; "
    "font-src 'self' data:; "
    "connect-src 'self' https:; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'; "
    "upgrade-insecure-requests"
)

# Dev: adiciona `ws:` pra HMR, `localhost:*` pra API, permite `unsafe-eval`
# (Nuxt dev runtime). `frame-ancestors 'none'` e `object-src 'none'` persistem.
DEFAULT_CSP_DEV = (
    "default-src 'self' http://localhost:* ws://localhost:*; "
    "script-src 'self' 'unsafe-eval' 'unsafe-inline' http://localhost:*; "
    "style-src 'self' 'unsafe-inline' http://localhost:*; "
    "img-src 'self' data: https: http://localhost:*; "
    "font-src 'self' data:; "
    "connect-src 'self' http://localhost:* ws://localhost:* https:; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)

DEFAULT_HSTS = "max-age=31536000; includeSubDomains"

DEFAULT_PERMISSIONS_POLICY = (
    "geolocation=(), "
    "microphone=(), "
    "camera=(), "
    "payment=(), "
    "usb=(), "
    "magnetometer=(), "
    "gyroscope=(), "
    "accelerometer=()"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Injeta CSP, HSTS e Permissions-Policy em toda response."""

    def __init__(
        self,
        app: ASGIApp,
        csp: str | None = None,
        enable_hsts: bool = True,
        hsts: str = DEFAULT_HSTS,
        permissions_policy: str = DEFAULT_PERMISSIONS_POLICY,
    ) -> None:
        super().__init__(app)
        self._csp = csp or DEFAULT_CSP_PROD
        self._enable_hsts = enable_hsts
        self._hsts = hsts
        self._permissions_policy = permissions_policy

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        # CSP — não sobrescreve se outro handler já setou (ex: rotas
        # que servem docs podem precisar de política mais frouxa).
        response.headers.setdefault("Content-Security-Policy", self._csp)
        if self._enable_hsts:
            # HSTS só faz sentido em HTTPS; mas header não causa dano em
            # HTTP (navegadores ignoram). Mantemos sempre em prod para
            # cobrir tunnels / reverse proxies.
            response.headers.setdefault("Strict-Transport-Security", self._hsts)
        response.headers.setdefault(
            "Permissions-Policy", self._permissions_policy
        )
        return response
