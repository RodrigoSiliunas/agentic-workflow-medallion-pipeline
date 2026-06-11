"""Unit tests do endpoint GET /pipelines/{id}/columns (colunas reais do builder)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.routes.pipeline_editor import list_table_columns
from app.services.pipeline_editor.manifest import load_manifest_for_template


def _auth():
    auth = MagicMock()
    auth.company_id = uuid.uuid4()
    return auth


def _manifest_patch(catalog: str):
    async def _resolve(db, pipeline):
        return load_manifest_for_template(
            "pipeline-seguradora-whatsapp", catalog=catalog
        )

    return _resolve


STMT_OK = {
    "status": {"state": "SUCCEEDED"},
    "result": {
        "data_array": [
            ["message_identity", "string", "YES", None],
            ["conversation_id", "string", "NO", "id da conversa"],
        ]
    },
}


@pytest.mark.asyncio
async def test_columns_endpoint_returns_real_schema():
    pipeline = MagicMock()
    with (
        patch(
            "app.api.routes.pipeline_editor._load_pipeline",
            new=AsyncMock(return_value=pipeline),
        ),
        patch(
            "app.api.routes.pipeline_editor._resolve_manifest",
            new=_manifest_patch("medallion_security"),
        ),
        patch("app.api.routes.pipeline_editor.DatabricksService") as svc_cls,
    ):
        svc_cls.return_value.query_table = AsyncMock(return_value=STMT_OK)
        out = await list_table_columns(
            uuid.uuid4(),
            table="medallion_security.silver.messages_clean",
            auth=_auth(),
            db=MagicMock(),
        )

    assert out["table"] == "medallion_security.silver.messages_clean"
    assert out["columns"][0] == {
        "name": "message_identity",
        "type": "string",
        "nullable": True,
        "comment": None,
    }
    assert out["columns"][1]["nullable"] is False
    # SQL consulta o information_schema do catalog certo, filtrando schema+tabela
    sql = svc_cls.return_value.query_table.call_args.args[0]
    assert "`medallion_security`.information_schema.columns" in sql
    assert "table_schema = 'silver'" in sql
    assert "table_name = 'messages_clean'" in sql


@pytest.mark.asyncio
async def test_columns_endpoint_blocks_table_fora_do_manifest():
    """Guard cross-tenant: tabela que nao pertence aos nodes Silver -> 400."""
    pipeline = MagicMock()
    with (
        patch(
            "app.api.routes.pipeline_editor._load_pipeline",
            new=AsyncMock(return_value=pipeline),
        ),
        patch(
            "app.api.routes.pipeline_editor._resolve_manifest",
            new=_manifest_patch("medallion_security"),
        ),
        patch("app.api.routes.pipeline_editor.DatabricksService") as svc_cls,
    ):
        svc_cls.return_value.query_table = AsyncMock()
        with pytest.raises(HTTPException) as exc:
            await list_table_columns(
                uuid.uuid4(),
                table="outro_catalog.silver.dados_alheios",
                auth=_auth(),
                db=MagicMock(),
            )

    assert exc.value.status_code == 400
    svc_cls.return_value.query_table.assert_not_called()


@pytest.mark.asyncio
async def test_columns_endpoint_propaga_falha_do_warehouse():
    pipeline = MagicMock()
    failed = {"status": {"state": "FAILED", "error": {"message": "warehouse off"}}}
    with (
        patch(
            "app.api.routes.pipeline_editor._load_pipeline",
            new=AsyncMock(return_value=pipeline),
        ),
        patch(
            "app.api.routes.pipeline_editor._resolve_manifest",
            new=_manifest_patch("medallion_security"),
        ),
        patch("app.api.routes.pipeline_editor.DatabricksService") as svc_cls,
    ):
        svc_cls.return_value.query_table = AsyncMock(return_value=failed)
        with pytest.raises(HTTPException) as exc:
            await list_table_columns(
                uuid.uuid4(),
                table="medallion_security.silver.messages_clean",
                auth=_auth(),
                db=MagicMock(),
            )

    assert exc.value.status_code == 502
    assert "warehouse off" in exc.value.detail
