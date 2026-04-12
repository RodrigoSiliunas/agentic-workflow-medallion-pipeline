"""Integration test — /observability/metrics agrega dados reais da empresa."""

import httpx
import pytest

pytestmark = pytest.mark.asyncio


async def test_metrics_shape_for_new_company(
    http_client: httpx.AsyncClient, auth_headers: dict
):
    response = await http_client.get(
        "/api/v1/observability/metrics", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()

    assert "company_id" in data
    assert data["deployments"]["total"] == 0
    # Company recem criada ja tem o pipeline default (via register-company)
    assert data["pipelines"]["total"] >= 1
    assert data["channels"]["total"] == 0
    # Observer metrics sao mockadas mas o shape deve estar certo
    assert data["observer"]["estimated_cost_usd"] > 0
