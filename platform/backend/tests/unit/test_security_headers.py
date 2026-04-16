"""Testes do SecurityHeadersMiddleware (T2 Phase 3).

Valida que CSP, HSTS e Permissions-Policy saem em todas as responses.
Usa TestClient do Starlette direto (sem subir o app inteiro do backend,
que exige DB/Redis).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.security_headers import (
    DEFAULT_CSP_DEV,
    DEFAULT_CSP_PROD,
    DEFAULT_HSTS,
    DEFAULT_PERMISSIONS_POLICY,
    SecurityHeadersMiddleware,
)


def _make_app(**middleware_kwargs) -> FastAPI:
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware, **middleware_kwargs)

    @app.get("/ping")
    def ping():
        return {"status": "ok"}

    return app


class TestHeadersPresent:
    def test_csp_default_prod_set(self):
        client = TestClient(_make_app())
        r = client.get("/ping")
        assert r.status_code == 200
        assert r.headers.get("Content-Security-Policy") == DEFAULT_CSP_PROD

    def test_custom_csp_override(self):
        custom = "default-src 'none'"
        client = TestClient(_make_app(csp=custom))
        r = client.get("/ping")
        assert r.headers.get("Content-Security-Policy") == custom

    def test_hsts_default_on(self):
        client = TestClient(_make_app())
        r = client.get("/ping")
        assert r.headers.get("Strict-Transport-Security") == DEFAULT_HSTS

    def test_hsts_disabled(self):
        client = TestClient(_make_app(enable_hsts=False))
        r = client.get("/ping")
        assert "Strict-Transport-Security" not in r.headers

    def test_permissions_policy_default(self):
        client = TestClient(_make_app())
        r = client.get("/ping")
        assert (
            r.headers.get("Permissions-Policy")
            == DEFAULT_PERMISSIONS_POLICY
        )


class TestCspContent:
    def test_prod_csp_has_critical_directives(self):
        for directive in (
            "default-src 'self'",
            "object-src 'none'",
            "frame-ancestors 'none'",
            "base-uri 'self'",
        ):
            assert directive in DEFAULT_CSP_PROD, directive

    def test_prod_csp_blocks_inline_scripts(self):
        assert "'unsafe-inline'" not in DEFAULT_CSP_PROD.split("script-src")[1].split(";")[0]

    def test_dev_csp_keeps_hardening_directives(self):
        # Mesmo em dev, object-src 'none' e frame-ancestors 'none' persistem.
        assert "object-src 'none'" in DEFAULT_CSP_DEV
        assert "frame-ancestors 'none'" in DEFAULT_CSP_DEV


class TestPermissionsPolicy:
    def test_denies_high_risk_features(self):
        for feature in (
            "geolocation",
            "microphone",
            "camera",
            "payment",
            "usb",
        ):
            assert f"{feature}=()" in DEFAULT_PERMISSIONS_POLICY


class TestDoesNotOverwriteExistingHeaders:
    def test_preserves_existing_csp_set_by_endpoint(self):
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/docs-like")
        def docs_like(response_kind: str = "loose"):
            from fastapi.responses import JSONResponse

            return JSONResponse(
                {"kind": response_kind},
                headers={"Content-Security-Policy": "default-src *"},
            )

        client = TestClient(app)
        r = client.get("/docs-like")
        # Endpoint CSP ganha prioridade
        assert r.headers.get("Content-Security-Policy") == "default-src *"
