"""Testes do DatabricksService (T7 Phase 4)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.databricks_service import DatabricksService


@pytest.fixture(autouse=True)
async def reset_shared_client():
    """Garante que cada teste começa e termina sem cliente compartilhado."""
    await DatabricksService.close()
    yield
    await DatabricksService.close()


def _make_service() -> DatabricksService:
    svc = DatabricksService(db=MagicMock(), company_id=uuid.uuid4())
    svc._host = "https://workspace.cloud.databricks.com"
    svc._token = "fake-token"  # noqa: S105
    return svc


class TestSharedClient:
    def test_client_is_shared_across_instances(self):
        svc1 = _make_service()
        svc2 = _make_service()
        assert svc1._client() is svc2._client()

    def test_client_persists_across_calls(self):
        svc = _make_service()
        c1 = svc._client()
        c2 = svc._client()
        assert c1 is c2

    @pytest.mark.asyncio
    async def test_close_clears_shared_client(self):
        svc = _make_service()
        svc._client()
        await DatabricksService.close()
        assert DatabricksService._shared_client is None

    @pytest.mark.asyncio
    async def test_close_is_idempotent(self):
        await DatabricksService.close()
        await DatabricksService.close()  # sem raise


class TestParallelSchemaFetch:
    @pytest.mark.asyncio
    async def test_get_table_schemas_fetches_all_three_schemas_in_parallel(self):
        svc = _make_service()
        svc._ensure_credentials = AsyncMock()

        call_log: list[str] = []

        async def mock_fetch(catalog, schema_name):
            call_log.append(schema_name)
            return [{"catalog": catalog, "schema": schema_name, "table": "t", "columns": []}]

        with patch.object(svc, "_fetch_schema", side_effect=mock_fetch):
            result = await svc.get_table_schemas("medallion")

        # Todas as 3 chamadas disparadas
        assert set(call_log) == {"bronze", "silver", "gold"}
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_one_schema_failure_does_not_abort_others(self):
        svc = _make_service()
        svc._ensure_credentials = AsyncMock()

        async def mock_fetch(catalog, schema_name):
            if schema_name == "silver":
                raise RuntimeError("silver unavailable")
            return [{"schema": schema_name}]

        with patch.object(svc, "_fetch_schema", side_effect=mock_fetch):
            result = await svc.get_table_schemas("medallion")

        # bronze + gold retornados; silver pulado
        schemas_got = {r["schema"] for r in result}
        assert schemas_got == {"bronze", "gold"}

    @pytest.mark.asyncio
    async def test_fetch_schema_returns_empty_on_non_200(self):
        svc = _make_service()
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch.object(DatabricksService, "_client", return_value=mock_client):
            result = await svc._fetch_schema("medallion", "bronze")

        assert result == []

    @pytest.mark.asyncio
    async def test_fetch_schema_parses_columns(self):
        svc = _make_service()
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "tables": [
                {
                    "name": "conversations",
                    "columns": [
                        {"name": "id", "type_name": "STRING"},
                        {"name": "ts", "type_name": "TIMESTAMP"},
                    ],
                }
            ]
        }
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch.object(DatabricksService, "_client", return_value=mock_client):
            result = await svc._fetch_schema("medallion", "bronze")

        assert len(result) == 1
        assert result[0]["table"] == "conversations"
        assert len(result[0]["columns"]) == 2


class TestClientConfig:
    def test_client_is_async_client_instance(self):
        svc = _make_service()
        client = svc._client()
        assert isinstance(client, httpx.AsyncClient)
