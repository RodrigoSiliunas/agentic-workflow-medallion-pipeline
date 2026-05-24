"""Pipeline Editor core — DSL, manifest, codegen e artefatos."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.pipeline_editor.artifacts import build_prompt_markdown
from app.services.pipeline_editor.codegen import generate_pyspark_patch
from app.services.pipeline_editor.manifest import (
    load_manifest_for_template,
    manifest_for_editor,
    silver_nodes,
)
from app.services.pipeline_editor.nl_agent import build_edit_proposal_from_nl
from app.services.pipeline_editor.preview import (
    build_export_result,
    build_preview_result,
    run_preview,
)
from app.services.pipeline_editor.preview_sql import (
    build_rows_after_sql,
    build_rows_before_sql,
    parse_query_result,
    preview_namespace,
)
from app.services.pipeline_editor.schemas import EditProposal, TransformDraft, TransformOperation


def test_transform_operation_validates_supported_operation():
    with pytest.raises(ValueError, match="Unsupported transform operation"):
        TransformOperation(
            op="drop_database",
            column="message_body",
        )


def test_transform_draft_requires_manifest_target_node():
    manifest = load_manifest_for_template("pipeline-seguradora-whatsapp")
    draft = TransformDraft(
        layer="silver",
        target_node="silver_dedup",
        target_table="medallion.silver.messages_clean",
        operations=[
            TransformOperation(op="rename_column", column="meta_city", new_name="cidade"),
            TransformOperation(op="drop_column", column="agent_notes"),
        ],
    )

    assert manifest.resolve_node(draft.target_node).task_key == "silver_dedup"
    assert draft.operations[0].new_name == "cidade"


def test_codegen_adds_generated_transform_block_before_delta_write():
    source = """
# DBTITLE 1,Salvar como Delta Table e Upload para S3
(
    df_parsed.write.format("delta")
    .mode("overwrite")
    .saveAsTable(SILVER_TABLE)
)
"""
    manifest = load_manifest_for_template("pipeline-seguradora-whatsapp")
    node = manifest.resolve_node("silver_dedup")
    draft = TransformDraft(
        layer="silver",
        target_node="silver_dedup",
        target_table="medallion.silver.messages_clean",
        input_dataframe="df_parsed",
        output_dataframe="df_editor",
        operations=[
            TransformOperation(op="rename_column", column="meta_city", new_name="cidade"),
            TransformOperation(op="drop_column", column="agent_notes"),
        ],
    )

    patched = generate_pyspark_patch(source, draft, node=node)

    assert "# DBTITLE 1,Transformacoes Low-Code do Pipeline Editor" in patched
    assert 'withColumnRenamed("meta_city", "cidade")' in patched
    assert '.drop("agent_notes")' in patched
    assert "df_editor.write.format" in patched
    assert "df_parsed.write.format" not in patched


def test_prompt_markdown_contains_context_and_redacts_secrets():
    session_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    draft = TransformDraft(
        layer="silver",
        target_node="silver_dedup",
        target_table="medallion.silver.messages_clean",
        operations=[TransformOperation(op="trim", column="sender_name")],
    )

    markdown = build_prompt_markdown(
        session_id=session_id,
        pipeline_name="Pipeline ACME",
        user_request="Trim sender_name usando token sk-live-secret",
        draft=draft,
        validation={"valid": True, "checks": ["syntax"]},
        preview={"row_count": 10},
    )

    assert "# Pipeline Editor Prompt" in markdown
    assert "Pipeline ACME" in markdown
    assert "sk-live-secret" not in markdown
    assert "[REDACTED]" in markdown
    assert "trim" in markdown


def test_preview_and_export_are_scoped_to_tenant_pipeline_and_session():
    company_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    pipeline_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    session_id = uuid.UUID("33333333-3333-3333-3333-333333333333")
    draft = TransformDraft(
        layer="silver",
        target_node="silver_dedup",
        target_table="medallion.silver.messages_clean",
        operations=[TransformOperation(op="drop_column", column="agent_notes")],
    )

    preview = build_preview_result(
        company_id=company_id,
        pipeline_id=pipeline_id,
        session_id=session_id,
        draft=draft,
        sample_rows=25,
        rows_after=[{"meta_city": "SP", "agent_notes": "x"}],
        status="ready",
    )
    export = build_export_result(
        company_id=company_id,
        pipeline_id=pipeline_id,
        session_id=session_id,
        export_format="parquet",
        preview_result=preview,
    )

    assert preview["company_id"] == str(company_id)
    assert preview["pipeline_id"] == str(pipeline_id)
    assert preview["session_id"] == str(session_id)
    assert preview["schema_delta"]["dropped"] == ["agent_notes"]
    assert export["format"] == "parquet"
    assert str(pipeline_id) in export["download_url"]
    assert str(session_id) in export["download_url"]


def test_manifest_for_editor_is_silver_only():
    manifest = load_manifest_for_template("pipeline-seguradora-whatsapp")
    editor_manifest = manifest_for_editor(manifest)

    assert len(editor_manifest.nodes) == len(silver_nodes(manifest))
    assert all(node.layer == "silver" for node in editor_manifest.nodes)
    assert not any(node.layer == "bronze" for node in editor_manifest.nodes)


def test_transform_draft_rejects_non_silver_layer():
    with pytest.raises(ValueError, match="Pipeline Editor suporta apenas camada Silver"):
        TransformDraft(
            layer="bronze",
            target_node="bronze_ingestion",
            target_table="medallion.bronze.conversations",
            operations=[],
        )


def test_preview_namespace_includes_company_pipeline_session():
    company_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    pipeline_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    session_id = uuid.UUID("33333333-3333-3333-3333-333333333333")

    namespace = preview_namespace(
        company_id=str(company_id),
        pipeline_id=str(pipeline_id),
        session_id=str(session_id),
    )

    assert namespace == "preview_11111111_22222222_33333333"


def test_build_rows_before_sql_quotes_table():
    sql = build_rows_before_sql("medallion.silver.messages_clean", 25)
    assert sql == "SELECT * FROM `medallion`.`silver`.`messages_clean` LIMIT 25"


def test_build_rows_after_sql_applies_rename_and_drop():
    operations = [
        TransformOperation(op="rename_column", column="meta_city", new_name="cidade"),
        TransformOperation(op="drop_column", column="agent_notes"),
    ]
    sql, warnings = build_rows_after_sql(
        "medallion.silver.messages_clean",
        ["meta_city", "agent_notes", "sender_name"],
        operations,
        10,
    )

    assert "`meta_city` AS `cidade`" in sql
    assert "agent_notes" not in sql.split("FROM", maxsplit=1)[0]
    assert "LIMIT 10" in sql
    assert warnings == []


def test_parse_query_result_builds_row_dicts():
    response = {
        "status": {"state": "SUCCEEDED"},
        "manifest": {
            "schema": {
                "columns": [
                    {"name": "meta_city"},
                    {"name": "sender_name"},
                ]
            }
        },
        "result": {"data_array": [["SP", "Ana"], ["RJ", "Bob"]]},
    }

    columns, rows = parse_query_result(response)

    assert columns == ["meta_city", "sender_name"]
    assert rows == [
        {"meta_city": "SP", "sender_name": "Ana"},
        {"meta_city": "RJ", "sender_name": "Bob"},
    ]


@pytest.mark.asyncio
async def test_run_preview_populates_rows_with_mocked_databricks():
    company_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    pipeline_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    session_id = uuid.UUID("33333333-3333-3333-3333-333333333333")
    draft = TransformDraft(
        layer="silver",
        target_node="silver_dedup",
        target_table="medallion.silver.messages_clean",
        operations=[TransformOperation(op="drop_column", column="agent_notes")],
    )

    before_response = {
        "status": {"state": "SUCCEEDED"},
        "manifest": {
            "schema": {
                "columns": [
                    {"name": "meta_city"},
                    {"name": "agent_notes"},
                ]
            }
        },
        "result": {"data_array": [["SP", "x"]]},
    }
    after_response = {
        "status": {"state": "SUCCEEDED"},
        "manifest": {"schema": {"columns": [{"name": "meta_city"}]}},
        "result": {"data_array": [["SP"]]},
    }

    databricks = MagicMock()
    databricks.query_table = AsyncMock(side_effect=[before_response, after_response])

    preview = await run_preview(
        databricks,
        company_id=company_id,
        pipeline_id=pipeline_id,
        session_id=session_id,
        draft=draft,
        sample_rows=5,
    )

    assert preview["status"] == "ready"
    assert preview["rows_before"] == [{"meta_city": "SP", "agent_notes": "x"}]
    assert preview["rows_after"] == [{"meta_city": "SP"}]
    assert preview["namespace"] == "preview_11111111_22222222_33333333"
    assert databricks.query_table.await_count == 2


@pytest.mark.asyncio
async def test_run_preview_marks_failed_on_sql_error():
    databricks = MagicMock()
    databricks.query_table = AsyncMock(
        return_value={
            "status": {
                "state": "FAILED",
                "error": {"message": "Table not found"},
            }
        }
    )

    preview = await run_preview(
        databricks,
        company_id=uuid.uuid4(),
        pipeline_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        draft=TransformDraft(
            layer="silver",
            target_node="silver_dedup",
            target_table="medallion.silver.messages_clean",
            operations=[],
        ),
        sample_rows=5,
    )

    assert preview["status"] == "failed"
    assert "Table not found" in preview["error"]


@pytest.mark.asyncio
async def test_nl_agent_uses_llm_tool_response():
    manifest = load_manifest_for_template("pipeline-seguradora-whatsapp")
    tool_input = {
        "explanation": "Renomeei meta_city para cidade.",
        "draft": {
            "layer": "silver",
            "target_node": "silver_dedup",
            "target_table": "medallion.silver.messages_clean",
            "operations": [
                {"op": "rename_column", "column": "meta_city", "new_name": "cidade"},
            ],
        },
        "risk_score": 2,
    }

    async def fake_stream(**kwargs):
        from observer.chat.base import ChatToolUseEvent

        yield ChatToolUseEvent(id="tool-1", name="submit_edit_proposal", input=tool_input)

    mock_provider = MagicMock()
    mock_provider.stream_with_tools = fake_stream

    with patch(
        "app.services.pipeline_editor.nl_agent._resolve_provider",
        AsyncMock(return_value=(mock_provider, "claude-sonnet-4-6")),
    ):
        proposal = await build_edit_proposal_from_nl(
            db=MagicMock(),
            company_id=uuid.uuid4(),
            user_message="renomeie meta_city para cidade",
            draft=None,
            manifest=manifest,
        )

    assert isinstance(proposal, EditProposal)
    assert proposal.draft.operations[0].new_name == "cidade"
    assert "Renomeei" in proposal.explanation


@pytest.mark.asyncio
async def test_nl_agent_falls_back_when_llm_disabled():
    manifest = load_manifest_for_template("pipeline-seguradora-whatsapp")

    with patch("app.services.pipeline_editor.nl_agent.settings") as mock_settings:
        mock_settings.PIPELINE_EDITOR_LLM_ENABLED = False
        proposal = await build_edit_proposal_from_nl(
            db=MagicMock(),
            company_id=uuid.uuid4(),
            user_message="remova agent_notes",
            draft=None,
            manifest=manifest,
        )

    assert proposal.draft.layer == "silver"
    assert "Proposta estruturada" in proposal.explanation
