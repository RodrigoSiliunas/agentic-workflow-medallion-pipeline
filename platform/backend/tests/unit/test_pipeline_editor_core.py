"""Pipeline Editor core — DSL, manifest, codegen e artefatos."""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.pipeline_editor.artifacts import build_prompt_markdown
from app.services.pipeline_editor.codegen import generate_pyspark_patch
from app.services.pipeline_editor.downstream_impact import (
    check_downstream_impact,
    find_column_references,
)
from app.services.pipeline_editor.manifest import (
    load_manifest_for_template,
    manifest_for_editor,
    silver_nodes,
)
from app.services.pipeline_editor.nl_agent import (
    _build_submit_tool,
    build_edit_proposal_from_nl,
)
from app.services.pipeline_editor.preview import (
    PreviewExportError,
    build_export_result,
    build_preview_result,
    run_preview,
)
from app.services.pipeline_editor.preview_sql import (
    PreviewSqlError,
    build_rows_after_sql,
    build_rows_before_sql,
    parse_query_result,
    preview_namespace,
    validate_target_table,
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
    manifest = load_manifest_for_template("pipeline-seguradora-whatsapp")
    node = manifest.resolve_node("silver_dedup")
    source = f"""
# DBTITLE 1,Parse Metadata JSON
df_parsed = df_clean.withColumns({{}})

{node.insertion_marker}
(
    df_parsed.write.format("delta")
    .mode("overwrite")
    .saveAsTable(SILVER_TABLE)
)
"""
    draft = TransformDraft(
        layer="silver",
        target_node="silver_dedup",
        target_table="medallion.silver.messages_clean",
        operations=[
            TransformOperation(op="rename_column", column="meta_city", new_name="cidade"),
            TransformOperation(op="drop_column", column="agent_notes"),
        ],
    )

    patched = generate_pyspark_patch(source, draft, node=node)

    assert "# DBTITLE 1,Transformacoes Low-Code do Pipeline Editor" in patched
    assert 'df_parsed = df_parsed.withColumnRenamed("meta_city", "cidade")' in patched
    assert 'df_parsed = df_parsed.drop("agent_notes")' in patched
    # write linha inalterada — sem troca de DF
    assert "df_parsed.write.format" in patched
    # sem magia df_editor/df_parsed mágico
    assert "df_editor" not in patched


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
        rows_before=[{"meta_city": "SP", "agent_notes": "x"}],
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


def test_build_preview_result_derives_schema_before_and_after():
    company_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    pipeline_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    session_id = uuid.UUID("33333333-3333-3333-3333-333333333333")
    draft = TransformDraft(
        layer="silver",
        target_node="silver_dedup",
        target_table="medallion.silver.messages_clean",
        operations=[
            TransformOperation(op="drop_column", column="agent_notes"),
            TransformOperation(op="rename_column", column="meta_city", new_name="city"),
            TransformOperation(
                op="derive_column", column="city_upper", expression="upper(city)"
            ),
        ],
    )

    preview = build_preview_result(
        company_id=company_id,
        pipeline_id=pipeline_id,
        session_id=session_id,
        draft=draft,
        sample_rows=25,
        rows_before=[{"meta_city": "SP", "agent_notes": "x", "phone": "123"}],
        status="ready",
    )

    # schema_before = colunas reais da tabela (ordem preservada)
    assert [c["name"] for c in preview["schema_before"]] == [
        "meta_city",
        "agent_notes",
        "phone",
    ]
    # schema_after = before com o delta aplicado (drop, rename, derive)
    after = preview["schema_after"]
    after_by_name = {c["name"]: c for c in after}
    assert "agent_notes" not in after_by_name  # dropped
    assert "city" in after_by_name and after_by_name["city"]["from"] == "meta_city"
    assert after_by_name["city"]["state"] == "renamed"
    assert "phone" in after_by_name  # unchanged passthrough
    assert after_by_name["city_upper"]["state"] == "derived"


def test_build_preview_result_failed_status_has_empty_schemas():
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
        status="failed",
        error="Databricks indisponivel",
    )

    # Defensivo: sem rows_before, schemas vem vazios (preview falhou)
    assert preview["status"] == "failed"
    assert preview["schema_before"] == []
    assert preview["schema_after"] == []


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
        output_tables=["medallion.silver.messages_clean"],
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
        output_tables=["medallion.silver.messages_clean"],
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


def test_codegen_uses_node_insertion_marker_not_hardcoded():
    """Regressao: codegen ignorava node.insertion_marker e hardcodava
    o marker de silver_dedup, derrubando edits em silver_entities/enrichment.
    """
    manifest = load_manifest_for_template("pipeline-seguradora-whatsapp")
    node = manifest.resolve_node("silver_entities")
    source = f"""
# DBTITLE 1,Redaction do message_body
df_redacted = df.withColumn("message_body", redact_udf("message_body"))

{node.insertion_marker}
(
    df_redacted.write.format("delta")
    .mode("overwrite")
    .saveAsTable("medallion.silver.messages_clean")
)
"""
    draft = TransformDraft(
        layer="silver",
        target_node="silver_entities",
        target_table="medallion.silver.messages_clean",
        operations=[TransformOperation(op="drop_column", column="cpfs_found")],
    )

    patched = generate_pyspark_patch(source, draft, node=node)

    assert node.insertion_marker in patched
    assert "# DBTITLE 1,Transformacoes Low-Code do Pipeline Editor" in patched
    assert 'df_redacted = df_redacted.drop("cpfs_found")' in patched
    # write inalterado — sem troca de string frágil
    assert "df_redacted.write.format" in patched
    assert "df_editor" not in patched


def test_manifest_silver_markers_exist_in_source_files():
    """Regressao: manifest declarava markers inexistentes em silver_entities
    e silver_enrichment. Garante que cada node.insertion_marker do silver
    aparece literalmente no arquivo apontado por node.file_path.
    """
    manifest = load_manifest_for_template("pipeline-seguradora-whatsapp")
    repo_root = Path(__file__).resolve().parents[4]

    errors: list[str] = []
    for node in silver_nodes(manifest):
        file_path = repo_root / node.file_path
        assert file_path.exists(), f"Arquivo do no `{node.id}` ausente: {file_path}"
        content = file_path.read_text(encoding="utf-8")
        if node.insertion_marker not in content:
            errors.append(
                f"{node.id}: marker `{node.insertion_marker}` ausente em {node.file_path}"
            )

    assert not errors, "Markers do manifest divergem dos arquivos:\n  " + "\n  ".join(errors)


@pytest.mark.parametrize(
    "node_id,op,op_kwargs,expected_fragment",
    [
        (
            "silver_dedup",
            "rename_column",
            {"column": "meta_city", "new_name": "cidade"},
            'df_parsed = df_parsed.withColumnRenamed("meta_city", "cidade")',
        ),
        (
            "silver_dedup",
            "cast_column",
            {"column": "meta_response_time_sec", "data_type": "double"},
            'df_parsed = df_parsed.withColumn("meta_response_time_sec", '
            'F.col("meta_response_time_sec").cast("double"))',
        ),
        (
            "silver_entities",
            "rename_column",
            {"column": "lead_name", "new_name": "nome_lead"},
            'df_redacted = df_redacted.withColumnRenamed("lead_name", "nome_lead")',
        ),
        (
            "silver_entities",
            "cast_column",
            {"column": "lead_phone", "data_type": "string"},
            'df_redacted = df_redacted.withColumn("lead_phone", '
            'F.col("lead_phone").cast("string"))',
        ),
        (
            "silver_enrichment",
            "rename_column",
            {"column": "city", "new_name": "cidade"},
            'conversations = conversations.withColumnRenamed("city", "cidade")',
        ),
        (
            "silver_enrichment",
            "cast_column",
            {"column": "duration_minutes", "data_type": "double"},
            'conversations = conversations.withColumn("duration_minutes", '
            'F.col("duration_minutes").cast("double"))',
        ),
    ],
)
def test_codegen_real_notebooks_rename_and_cast(node_id, op, op_kwargs, expected_fragment):
    """DoD C1: patch contra notebook real usa DF correto, sem df_editor/df_parsed mágico."""
    manifest = load_manifest_for_template("pipeline-seguradora-whatsapp")
    node = manifest.resolve_node(node_id)
    repo_root = Path(__file__).resolve().parents[4]
    source = (repo_root / node.file_path).read_text(encoding="utf-8")

    draft = TransformDraft(
        layer="silver",
        target_node=node_id,
        target_table=node.output_tables[0],
        operations=[TransformOperation(op=op, **op_kwargs)],
    )

    patched = generate_pyspark_patch(source, draft, node=node)

    # (a) usa o DF de escrita correto do node
    assert expected_fragment in patched, (
        f"Fragmento esperado ausente em {node_id}:\n  {expected_fragment}"
    )
    # (b) sem df_editor ou inicialização mágica df_X = df_Y
    assert "df_editor" not in patched
    assert f"df_editor = {node.write_dataframe}" not in patched
    # (c) compila sem SyntaxError
    compile(patched, f"<{node_id}_patched>", "exec")
    # (d) write original ainda usa o DF correto
    assert f"{node.write_dataframe}.write.format" in patched


def test_codegen_node_without_write_dataframe_raises():
    """Nodes sem write_dataframe levantam ValueError descritivo."""
    from app.services.pipeline_editor.manifest import PipelineManifestNode

    node = PipelineManifestNode(
        id="bronze_ingestion",
        layer="bronze",
        task_key="bronze_ingestion",
        file_path="any/path.py",
        insertion_marker="# marker",
    )
    draft = TransformDraft(
        layer="silver",
        target_node="silver_dedup",
        target_table="medallion.silver.messages_clean",
        operations=[],
    )

    with pytest.raises(ValueError, match="write_dataframe"):
        generate_pyspark_patch("# marker\ncode", draft, node=node)


def test_validate_generated_files_rejects_notebook_with_undefined_symbol():
    """Regressao C2: fix gerado com simbolo inexistente e rejeitado antes do PR."""
    try:
        import subprocess as _sp

        _sp.run(["ruff", "--version"], capture_output=True, timeout=5)
    except (FileNotFoundError, _sp.TimeoutExpired):
        pytest.skip("ruff nao disponivel")

    manifest = load_manifest_for_template("pipeline-seguradora-whatsapp")
    node = manifest.resolve_node("silver_dedup")

    # Notebook onde df_inexistente nunca e definido
    source = (
        "# Databricks notebook source\n"
        "df_parsed = spark.read.table('medallion.bronze.conversations')\n"
        f"\n{node.insertion_marker}\n"
        "(\n"
        "    df_parsed.write.format('delta')\n"
        "    .mode('overwrite')\n"
        "    .saveAsTable('medallion.silver.messages_clean')\n"
        ")\n"
    )
    # Injeta manualmente um bloco com variavel inexistente antes do marker
    bad_source = source.replace(
        node.insertion_marker,
        (
            "# COMMAND ----------\n\n"
            "# DBTITLE 1,Transformacoes Low-Code do Pipeline Editor\n"
            "df_parsed = df_inexistente.drop('agent_notes')\n\n"
            + node.insertion_marker
        ),
    )

    from app.services.pipeline_editor.secure_pr import validate_generated_files

    _, validation = validate_generated_files(
        source_by_path={node.file_path: bad_source},
        draft=TransformDraft(
            layer="silver",
            target_node="silver_dedup",
            target_table="medallion.silver.messages_clean",
            operations=[],  # Sem operacoes — source_by_path ja contem o bloco ruim
        ),
        manifest=manifest,
    )

    assert validation["valid"] is False
    assert any(
        "F821" in e or "inexistente" in e.lower() for e in validation["errors"]
    )


def test_validate_generated_files_accepts_notebook_with_valid_code():
    """Regressao C2: fix valido com variaveis corretas passa na validacao."""
    try:
        import subprocess as _sp

        _sp.run(["ruff", "--version"], capture_output=True, timeout=5)
    except (FileNotFoundError, _sp.TimeoutExpired):
        pytest.skip("ruff nao disponivel")

    manifest = load_manifest_for_template("pipeline-seguradora-whatsapp")
    node = manifest.resolve_node("silver_dedup")

    # Notebook com df_parsed definido antes do bloco gerado
    source = (
        "# Databricks notebook source\n"
        "df_parsed = spark.read.table('medallion.bronze.conversations')\n"
        f"\n{node.insertion_marker}\n"
        "(\n"
        "    df_parsed.write.format('delta')\n"
        "    .mode('overwrite')\n"
        "    .saveAsTable('medallion.silver.messages_clean')\n"
        ")\n"
    )

    draft = TransformDraft(
        layer="silver",
        target_node="silver_dedup",
        target_table="medallion.silver.messages_clean",
        operations=[
            TransformOperation(op="rename_column", column="meta_city", new_name="cidade"),
        ],
    )

    from app.services.pipeline_editor.secure_pr import validate_generated_files

    _, validation = validate_generated_files(
        source_by_path={node.file_path: source},
        draft=draft,
        manifest=manifest,
    )

    assert validation["valid"] is True


def test_nl_tool_target_node_enum_includes_silver_nodes():
    """Regressao: target_node era string aberta; LLM podia inventar/divergir.
    Agora o tool schema injeta enum com IDs dos nos Silver disponiveis.
    """
    manifest = load_manifest_for_template("pipeline-seguradora-whatsapp")
    expected_ids = {node.id for node in silver_nodes(manifest)}

    tool = _build_submit_tool(manifest)
    target_node_schema = tool.input_schema["properties"]["draft"]["properties"]["target_node"]

    assert "enum" in target_node_schema
    assert set(target_node_schema["enum"]) == expected_ids
    assert "bronze_ingestion" not in target_node_schema["enum"]
    assert "gold_analytics" not in target_node_schema["enum"]


# ---------------------------------------------------------------------------
# Fase C3 — Guard de impacto downstream
# ---------------------------------------------------------------------------

SENTIMENT_STUB = """\
filter_df = df.filter(
    (F.col("direction") == "inbound") & (F.col("message_body").isNotNull())
)
words = filter_df.withColumn(
    "positive_words",
    F.expr(f"filter(split(lower(message_body), ' '), x -> x rlike 'bom')"),
)
"""

CHURN_STUB = """\
df2 = df.select("conversation_id", "timestamp", "message_body", "conversation_outcome")
df3 = df2.withColumn("reactivation_message", F.col("message_body").alias("rm"))
"""

UNRELATED_STUB = """\
df = spark.read.table("medallion.silver.conversations_enriched")
df2 = df.groupBy("conversation_id").agg(F.sum("duration_minutes").alias("total_minutes"))
"""


def test_find_column_references_locates_occurrences():
    refs = find_column_references("message_body", SENTIMENT_STUB, "gold/sentiment.py")

    assert len(refs) >= 2
    files = {r.file for r in refs}
    assert files == {"gold/sentiment.py"}
    lines = [r.line for r in refs]
    snippets = [r.snippet for r in refs]
    assert all(isinstance(ln, int) and ln > 0 for ln in lines)
    assert all("message_body" in s for s in snippets)


def test_find_column_references_returns_empty_for_unrelated():
    refs = find_column_references("message_body", UNRELATED_STUB, "gold/temporal.py")
    assert refs == []


def test_find_column_references_respects_word_boundary():
    source = "old_message_body = df.col\nmessage_body_backup = x\nmessage_body = real"
    refs = find_column_references("message_body", source, "f.py")
    # Apenas a linha "message_body = real" tem word boundary correto
    assert len(refs) == 1
    assert refs[0].line == 3


def test_check_downstream_impact_rename_blocked_with_references():
    draft = TransformDraft(
        layer="silver",
        target_node="silver_dedup",
        target_table="medallion.silver.messages_clean",
        operations=[
            TransformOperation(op="rename_column", column="message_body", new_name="corpo")
        ],
    )
    sources = {
        "gold/sentiment.py": SENTIMENT_STUB,
        "gold/churn.py": CHURN_STUB,
        "gold/temporal.py": UNRELATED_STUB,
    }

    impact = check_downstream_impact(draft, sources)

    assert impact["blocked"] is True
    assert len(impact["affected"]) == 1
    entry = impact["affected"][0]
    assert entry["column"] == "message_body"
    assert entry["op"] == "rename_column"
    # Apenas arquivos com referência devem aparecer
    ref_files = {r["file"] for r in entry["references"]}
    assert "gold/sentiment.py" in ref_files
    assert "gold/churn.py" in ref_files
    assert "gold/temporal.py" not in ref_files


def test_check_downstream_impact_drop_blocked():
    draft = TransformDraft(
        layer="silver",
        target_node="silver_dedup",
        target_table="medallion.silver.messages_clean",
        operations=[TransformOperation(op="drop_column", column="message_body")],
    )
    sources = {"gold/sentiment.py": SENTIMENT_STUB}

    impact = check_downstream_impact(draft, sources)

    assert impact["blocked"] is True
    assert impact["affected"][0]["op"] == "drop_column"


def test_check_downstream_impact_unreferenced_column_not_blocked():
    draft = TransformDraft(
        layer="silver",
        target_node="silver_dedup",
        target_table="medallion.silver.messages_clean",
        operations=[TransformOperation(op="rename_column", column="agent_notes", new_name="notas")],
    )
    sources = {
        "gold/sentiment.py": SENTIMENT_STUB,
        "gold/temporal.py": UNRELATED_STUB,
    }

    impact = check_downstream_impact(draft, sources)

    assert impact["blocked"] is False
    assert impact["affected"] == []


def test_check_downstream_impact_cast_not_blocked():
    """cast_column não está nas operações bloqueantes — apenas avisa."""
    draft = TransformDraft(
        layer="silver",
        target_node="silver_dedup",
        target_table="medallion.silver.messages_clean",
        operations=[
            TransformOperation(op="cast_column", column="message_body", data_type="string")
        ],
    )
    sources = {"gold/sentiment.py": SENTIMENT_STUB}

    impact = check_downstream_impact(draft, sources)

    assert impact["blocked"] is False
    assert impact["affected"] == []


def test_check_downstream_impact_empty_sources():
    draft = TransformDraft(
        layer="silver",
        target_node="silver_dedup",
        target_table="medallion.silver.messages_clean",
        operations=[TransformOperation(op="rename_column", column="message_body", new_name="x")],
    )

    impact = check_downstream_impact(draft, {})

    assert impact["blocked"] is False
    assert impact["affected"] == []


def test_whatsapp_manifest_has_downstream_scan_paths():
    manifest = load_manifest_for_template("pipeline-seguradora-whatsapp")

    assert len(manifest.downstream_scan_paths) > 0
    # Contém notebooks gold e validation
    paths_str = " ".join(manifest.downstream_scan_paths)
    assert "gold/" in paths_str
    assert "validation/checks.py" in paths_str


def test_check_downstream_impact_real_gold_notebooks():
    """DoD C3: rename message_body retorna os gold/validation afetados reais."""
    manifest = load_manifest_for_template("pipeline-seguradora-whatsapp")
    repo_root = Path(__file__).resolve().parents[4]

    # Carrega os notebooks reais do repo
    sources: dict[str, str] = {}
    for path in manifest.downstream_scan_paths:
        full = repo_root / path
        if full.exists():
            sources[path] = full.read_text(encoding="utf-8")

    draft = TransformDraft(
        layer="silver",
        target_node="silver_dedup",
        target_table="medallion.silver.messages_clean",
        operations=[
            TransformOperation(op="rename_column", column="message_body", new_name="corpo_mensagem")
        ],
    )

    impact = check_downstream_impact(draft, sources)

    assert impact["blocked"] is True
    affected_files = {r["file"] for r in impact["affected"][0]["references"]}
    # Os notebooks sabidamente afetados devem aparecer
    assert any("sentiment.py" in f for f in affected_files)
    assert any("churn_reengagement.py" in f for f in affected_files)
    assert any("checks.py" in f for f in affected_files)


# ---------------------------------------------------------------------------
# #5 — Validacao de target_table contra node.output_tables
# ---------------------------------------------------------------------------


def test_validate_target_table_accepts_declared_output_table():
    """Tabela alvo declarada no node passa (case/crase-insensitive)."""
    output_tables = ["medallion.silver.messages_clean", "medallion.silver.leads_profile"]
    # Match exato
    validate_target_table("medallion.silver.messages_clean", output_tables)
    # Match normalizado (case + crases) ainda deve passar
    validate_target_table("Medallion.Silver.`leads_profile`", output_tables)


def test_validate_target_table_rejects_arbitrary_table():
    """Tabela fora das output_tables do node e rejeitada (anti cross-tenant)."""
    output_tables = ["medallion.silver.messages_clean"]
    with pytest.raises(PreviewSqlError, match="nao pertence ao node"):
        validate_target_table("medallion.gold.secret_revenue", output_tables)
    # Mesmo schema, tabela nao declarada -> rejeita
    with pytest.raises(PreviewSqlError, match="nao pertence ao node"):
        validate_target_table("medallion.silver.outra_empresa", output_tables)


def test_validate_target_table_rejects_when_node_declares_nothing():
    """Node sem output_tables bloqueia preview/export por seguranca."""
    with pytest.raises(PreviewSqlError, match="nao declara output_tables"):
        validate_target_table("medallion.silver.messages_clean", [])


def test_validate_target_table_honors_wildcard_prefix():
    """Wildcard (ex.: medallion.gold.*) cobre o schema, mas nao outros schemas."""
    output_tables = ["medallion.gold.*"]
    validate_target_table("medallion.gold.funnel", output_tables)
    with pytest.raises(PreviewSqlError, match="nao pertence ao node"):
        validate_target_table("medallion.silver.messages_clean", output_tables)


def test_validate_target_table_matches_real_silver_node():
    """Cada Silver node do manifest aceita sua propria output_table."""
    manifest = load_manifest_for_template("pipeline-seguradora-whatsapp")
    for node in silver_nodes(manifest):
        for table in node.output_tables:
            validate_target_table(table, node.output_tables)


@pytest.mark.asyncio
async def test_run_preview_rejects_target_table_outside_node_output_tables():
    """Preview e marcado como failed quando target_table nao bate com o node."""
    draft = TransformDraft(
        layer="silver",
        target_node="silver_dedup",
        target_table="medallion.gold.secret_revenue",  # tabela arbitraria
        operations=[],
    )
    databricks = MagicMock()
    databricks.query_table = AsyncMock()

    preview = await run_preview(
        databricks,
        company_id=uuid.uuid4(),
        pipeline_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        draft=draft,
        sample_rows=5,
        output_tables=["medallion.silver.messages_clean"],
    )

    assert preview["status"] == "failed"
    assert "nao pertence ao node" in preview["error"]
    # Nenhuma query deve ter sido executada contra a tabela arbitraria
    databricks.query_table.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_preview_runs_when_target_table_is_declared():
    """Preview prossegue normalmente quando a target_table pertence ao node."""
    draft = TransformDraft(
        layer="silver",
        target_node="silver_dedup",
        target_table="medallion.silver.messages_clean",
        operations=[TransformOperation(op="drop_column", column="agent_notes")],
    )
    before_response = {
        "status": {"state": "SUCCEEDED"},
        "manifest": {
            "schema": {"columns": [{"name": "meta_city"}, {"name": "agent_notes"}]}
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
        company_id=uuid.uuid4(),
        pipeline_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        draft=draft,
        sample_rows=5,
        output_tables=["medallion.silver.messages_clean"],
    )

    assert preview["status"] == "ready"
    assert databricks.query_table.await_count == 2


def test_build_export_result_rejects_target_table_outside_node_output_tables():
    """Export revalida a tabela do preview persistido contra o manifest."""
    company_id = uuid.uuid4()
    pipeline_id = uuid.uuid4()
    session_id = uuid.uuid4()
    # Preview persistido aponta para tabela arbitraria (draft alterado pos-preview)
    preview_result = {
        "status": "ready",
        "target_table": "medallion.gold.secret_revenue",
        "rows_after": [{"col": "1"}],
    }

    with pytest.raises(PreviewExportError, match="nao pertence ao node"):
        build_export_result(
            company_id=company_id,
            pipeline_id=pipeline_id,
            session_id=session_id,
            export_format="csv",
            preview_result=preview_result,
            output_tables=["medallion.silver.messages_clean"],
        )


def test_build_export_result_allows_declared_target_table():
    """Export prossegue quando a tabela do preview pertence ao node."""
    preview_result = {
        "status": "ready",
        "target_table": "medallion.silver.messages_clean",
        "rows_after": [{"meta_city": "SP"}],
    }

    export = build_export_result(
        company_id=uuid.uuid4(),
        pipeline_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        export_format="csv",
        preview_result=preview_result,
        output_tables=["medallion.silver.messages_clean"],
    )

    assert export["format"] == "csv"
    assert export["row_count"] == 1
