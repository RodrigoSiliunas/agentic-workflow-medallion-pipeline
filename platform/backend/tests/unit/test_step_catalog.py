"""Unit tests para CatalogStep — validacao do nome do catalog + multi-tenant."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.real_saga.base import (
    DeploymentCredentials,
    SharedSagaState,
)
from app.services.real_saga.steps.catalog import (
    _IDENTIFIER_RE,
    _UC_NAME_RE,
    CatalogStep,
    _resolve_project,
)


class TestCatalogNameValidation:
    def test_catalog_name_validation_accepts_valid(self):
        """'medallion' deve ser aceito pelo regex."""
        assert _IDENTIFIER_RE.match("medallion") is not None

    def test_catalog_name_validation_accepts_with_numbers(self):
        """Nome com numeros e underscores deve ser aceito."""
        assert _IDENTIFIER_RE.match("medallion_v2") is not None

    def test_catalog_name_validation_rejects_injection(self):
        """'medallion; DROP' nao deve ser aceito — previne SQL injection."""
        assert _IDENTIFIER_RE.match("medallion; DROP") is None

    def test_catalog_name_validation_rejects_uppercase(self):
        """'Medallion' (com maiuscula) nao deve ser aceito."""
        assert _IDENTIFIER_RE.match("Medallion") is None

    def test_catalog_name_validation_rejects_starting_with_number(self):
        """Nome comecando com numero nao deve ser aceito."""
        assert _IDENTIFIER_RE.match("2catalog") is None

    def test_catalog_name_validation_rejects_empty(self):
        """String vazia nao deve ser aceita."""
        assert _IDENTIFIER_RE.match("") is None

    def test_catalog_name_validation_rejects_too_long(self):
        """Nomes com mais de 64 caracteres nao devem ser aceitos."""
        long_name = "a" * 65
        assert _IDENTIFIER_RE.match(long_name) is None

    def test_catalog_name_validation_accepts_max_length(self):
        """Nome com exatamente 64 caracteres deve ser aceito."""
        name_64 = "a" * 64
        assert _IDENTIFIER_RE.match(name_64) is not None


class TestProjectNameValidation:
    def test_accepts_hyphens_and_underscores(self):
        assert _UC_NAME_RE.match("acme-corp_v2") is not None

    def test_rejects_sql_injection(self):
        assert _UC_NAME_RE.match("acme; DROP TABLE") is None

    def test_rejects_empty(self):
        assert _UC_NAME_RE.match("") is None

    def test_resolve_project_uses_env_var(self):
        ctx = _make_ctx(env={"project_name": "acme-insurance"})
        assert _resolve_project(ctx) == "acme-insurance"

    def test_resolve_project_defaults(self):
        ctx = _make_ctx(env={})
        assert _resolve_project(ctx) == "medallion-pipeline"

    def test_resolve_project_rejects_invalid(self):
        ctx = _make_ctx(env={"project_name": "bad; name"})
        with pytest.raises(ValueError, match="project_name invalido"):
            _resolve_project(ctx)


class TestMultiTenantNaming:
    """Nomes de storage credential + external location devem ser prefixados
    por project_name — permite N deployments no mesmo workspace sem colisão."""

    @pytest.mark.asyncio
    async def test_execute_uses_project_prefixed_names(self, monkeypatch):
        step = CatalogStep()
        captured: dict[str, str] = {}

        async def _fake_cred(ctx, w, cred_name, role_arn):
            captured["cred_name"] = cred_name
            captured["role_arn"] = role_arn
            # Retorna external_id gerado pelo Databricks
            return "dbx-generated-external-id"

        async def _fake_loc(ctx, w, loc_name, cred_name, bucket, prefix=""):
            captured["loc_name"] = loc_name
            captured["loc_cred_name"] = cred_name
            captured["bucket"] = bucket
            captured["prefix"] = prefix

        async def _fake_catalog(ctx, w, catalog, managed_location=None):
            captured["catalog"] = catalog
            captured["managed_location"] = managed_location or ""

        async def _fake_schema(ctx, w, catalog, schema):
            return

        async def _fake_update_trust(ctx, role_arn, external_id):
            captured["trust_role_arn"] = role_arn
            captured["trust_external_id"] = external_id

        monkeypatch.setattr(
            CatalogStep, "_ensure_storage_credential", staticmethod(_fake_cred)
        )
        monkeypatch.setattr(
            CatalogStep, "_ensure_external_location", staticmethod(_fake_loc)
        )
        monkeypatch.setattr(
            CatalogStep, "_ensure_catalog", staticmethod(_fake_catalog)
        )
        monkeypatch.setattr(
            CatalogStep, "_ensure_schema", staticmethod(_fake_schema)
        )
        monkeypatch.setattr(
            "app.services.real_saga.steps.iam.update_trust_policy_with_external_id",
            _fake_update_trust,
        )
        monkeypatch.setattr(
            "app.services.real_saga.steps.catalog.workspace_client",
            lambda creds: MagicMock(),
        )

        ctx = _make_ctx(
            env={"project_name": "acme-insurance", "catalog": "medallion"},
            shared=SharedSagaState(
                s3_bucket="acme-insurance-datalake",
                databricks_role_arn="arn:aws:iam::1:role/acme-insurance-databricks-role",
            ),
        )
        await step.execute(ctx)

        # Nomes incluem company_suffix (primeiros 8 chars do UUID company_id)
        company_suffix = str(ctx.company_id).split("-")[0]
        expected_cred = f"acme-insurance-{company_suffix}-s3-credential"
        expected_loc = f"acme-insurance-{company_suffix}-datalake"
        assert captured["cred_name"] == expected_cred
        assert captured["loc_name"] == expected_loc
        assert captured["loc_cred_name"] == expected_cred
        assert captured["bucket"] == "acme-insurance-datalake"
        # Trust policy atualizada com external_id retornado pelo Databricks
        assert captured["trust_external_id"] == "dbx-generated-external-id"
        assert ctx.shared.databricks_external_id == "dbx-generated-external-id"
        assert ctx.shared.databricks_storage_credential == expected_cred
        assert ctx.shared.databricks_external_location == expected_loc

    @pytest.mark.asyncio
    async def test_execute_skips_uc_when_no_role_or_bucket(self, monkeypatch):
        """Sem role_arn OU sem bucket — pula credential/location, ainda cria catalog/schemas."""
        step = CatalogStep()
        cred_calls = 0
        loc_calls = 0

        async def _fake_cred(*a, **kw):
            nonlocal cred_calls
            cred_calls += 1

        async def _fake_loc(*a, **kw):
            nonlocal loc_calls
            loc_calls += 1

        async def _fake_catalog(ctx, w, catalog, managed_location=None):
            return

        async def _fake_schema(ctx, w, catalog, schema):
            return

        monkeypatch.setattr(
            CatalogStep, "_ensure_storage_credential", staticmethod(_fake_cred)
        )
        monkeypatch.setattr(
            CatalogStep, "_ensure_external_location", staticmethod(_fake_loc)
        )
        monkeypatch.setattr(
            CatalogStep, "_ensure_catalog", staticmethod(_fake_catalog)
        )
        monkeypatch.setattr(
            CatalogStep, "_ensure_schema", staticmethod(_fake_schema)
        )
        monkeypatch.setattr(
            "app.services.real_saga.steps.catalog.workspace_client",
            lambda creds: MagicMock(),
        )

        ctx = _make_ctx(
            env={"catalog": "medallion"},
            shared=SharedSagaState(),  # sem role nem bucket
        )
        await step.execute(ctx)

        assert cred_calls == 0
        assert loc_calls == 0


def _make_ctx(env, shared=None):
    import uuid as _uuid

    ctx = MagicMock()
    ctx.env_vars.return_value = env
    # company_id deterministico — eh usado pra prefixar nomes UC
    # multi-tenant em catalog.py, MagicMock auto-attr quebra str()
    ctx.company_id = _uuid.UUID("acedface-1234-5678-9abc-def012345678")
    ctx.credentials = DeploymentCredentials(
        aws_access_key_id="AKIA",
        aws_secret_access_key="sec",
        aws_region="us-east-2",
        databricks_host="https://dbc.cloud.databricks.com",
        databricks_token="dapi",
    )
    ctx.shared = shared or SharedSagaState()

    async def _noop_log(*args, **kwargs):
        return None

    ctx.info = _noop_log
    ctx.success = _noop_log
    return ctx
