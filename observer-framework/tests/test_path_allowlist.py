"""Testes do allowlist de paths do Observer (T1 Phase 2)."""

from __future__ import annotations

import pytest

from observer.providers.path_allowlist import (
    ALLOWED_PATH_PREFIXES,
    DisallowedPathError,
    is_path_allowed,
    validate_fixes,
    validate_path,
)

ALLOWED_SAMPLES = [
    "pipelines/pipeline-seguradora-whatsapp/notebooks/bronze/ingest.py",
    "observer-framework/observer/providers/anthropic_provider.py",
    "observer-framework/tests/test_foo.py",
    "platform/backend/app/services/saga.py",
    "platform/frontend/app/components/atoms/Button.vue",
]

DENIED_SAMPLES = [
    ".github/workflows/exfil.yml",
    "infra/aws/01-foundation/terraform.tfvars",
    "deploy/production.sh",
    "platform/backend/app/services/secret_reader.py",
    "platform/backend/app/secrets.py",
    "observer-framework/observer/secrets_config.py",
    ".env",
    ".env.prod",
    "credentials.json",
    "id_rsa",
    "server.key",
    "cert.pem",
    "random/outside/path.py",
    "docs/README.md",
]


class TestValidatePath:
    @pytest.mark.parametrize("path", ALLOWED_SAMPLES)
    def test_allowed_paths_pass(self, path: str):
        assert validate_path(path) == path.lstrip("/")
        assert is_path_allowed(path)

    @pytest.mark.parametrize("path", DENIED_SAMPLES)
    def test_denied_paths_raise(self, path: str):
        with pytest.raises(DisallowedPathError):
            validate_path(path)
        assert not is_path_allowed(path)

    def test_empty_path_raises(self):
        with pytest.raises(DisallowedPathError):
            validate_path("")

    def test_path_traversal_rejected(self):
        with pytest.raises(DisallowedPathError):
            validate_path("pipelines/../.github/workflows/evil.yml")

    def test_backslash_normalized(self):
        # Allowlist deve aceitar paths com separadores Windows também
        normalized = validate_path(
            "observer-framework\\observer\\providers\\base.py"
        )
        assert normalized.startswith("observer-framework/observer/")

    def test_leading_slash_stripped(self):
        assert validate_path("/pipelines/foo/bar.py").startswith("pipelines/")

    def test_allowed_prefixes_are_prefixes(self):
        # Guard: todo prefixo deve terminar com `/` para evitar match parcial
        for prefix in ALLOWED_PATH_PREFIXES:
            assert prefix.endswith("/"), f"{prefix!r} deve terminar com '/'"


class TestValidateFixes:
    def test_all_fixes_valid(self):
        fixes = [
            {"file_path": p, "code": "x"} for p in ALLOWED_SAMPLES[:2]
        ]
        validated = validate_fixes(fixes)
        assert len(validated) == 2
        assert all("file_path" in f and "code" in f for f in validated)

    def test_one_invalid_aborts_all(self):
        fixes = [
            {"file_path": ALLOWED_SAMPLES[0], "code": "x"},
            {"file_path": ".github/workflows/evil.yml", "code": "bad"},
        ]
        with pytest.raises(DisallowedPathError):
            validate_fixes(fixes)

    def test_preserves_code_field(self):
        fixes = [{"file_path": ALLOWED_SAMPLES[0], "code": "print(1)"}]
        validated = validate_fixes(fixes)
        assert validated[0]["code"] == "print(1)"
