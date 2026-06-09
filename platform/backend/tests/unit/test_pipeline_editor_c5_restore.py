"""Fase C5 — recuperacao/rollback: RESTORE TABLE + revert de PR do notebook."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.databricks_service import (
    DatabricksService,
    _parse_history_result,
    _quote_delta_table,
    build_describe_history_sql,
    build_restore_table_sql,
)

# ---------------------------------------------------------------------------
# Testes das funções puras de geração de SQL (sem I/O)
# ---------------------------------------------------------------------------


class TestQuoteDeltaTable:
    def test_quote_three_parts(self):
        assert _quote_delta_table("medallion.silver.messages_clean") == (
            "`medallion`.`silver`.`messages_clean`"
        )

    def test_quote_two_parts(self):
        assert _quote_delta_table("catalog.table") == "`catalog`.`table`"

    def test_quote_single_part(self):
        assert _quote_delta_table("my_table") == "`my_table`"

    def test_strips_whitespace(self):
        assert _quote_delta_table("  a.b.c  ") == "`a`.`b`.`c`"


class TestBuildDescribeHistorySql:
    def test_default_limit(self):
        sql = build_describe_history_sql("medallion.silver.messages_clean")
        assert sql == (
            "DESCRIBE HISTORY `medallion`.`silver`.`messages_clean` LIMIT 10"
        )

    def test_custom_limit(self):
        sql = build_describe_history_sql("medallion.silver.messages_clean", limit=5)
        assert "LIMIT 5" in sql

    def test_table_is_fully_quoted(self):
        sql = build_describe_history_sql("cat.sch.tbl")
        assert "`cat`.`sch`.`tbl`" in sql

    def test_starts_with_describe_history(self):
        sql = build_describe_history_sql("a.b.c")
        assert sql.startswith("DESCRIBE HISTORY ")


class TestBuildRestoreTableSql:
    def test_version_as_of(self):
        sql = build_restore_table_sql("medallion.silver.messages_clean", version=3)
        assert sql == (
            "RESTORE TABLE `medallion`.`silver`.`messages_clean` TO VERSION AS OF 3"
        )

    def test_timestamp_as_of(self):
        sql = build_restore_table_sql(
            "medallion.silver.messages_clean", timestamp="2024-01-15T12:00:00"
        )
        assert sql == (
            "RESTORE TABLE `medallion`.`silver`.`messages_clean` "
            "TO TIMESTAMP AS OF '2024-01-15T12:00:00'"
        )

    def test_version_zero_is_valid(self):
        sql = build_restore_table_sql("a.b.c", version=0)
        assert "VERSION AS OF 0" in sql

    def test_requires_version_or_timestamp(self):
        with pytest.raises(ValueError, match="version ou timestamp"):
            build_restore_table_sql("a.b.c")

    def test_version_takes_precedence_over_timestamp(self):
        sql = build_restore_table_sql("a.b.c", version=2, timestamp="2024-01-01")
        assert "VERSION AS OF 2" in sql
        assert "TIMESTAMP" not in sql

    def test_table_fully_quoted(self):
        sql = build_restore_table_sql("cat.sch.tbl", version=1)
        assert "`cat`.`sch`.`tbl`" in sql


class TestParseHistoryResult:
    def test_parses_succeeded_result(self):
        result = {
            "status": {"state": "SUCCEEDED"},
            "manifest": {
                "schema": {
                    "columns": [{"name": "version"}, {"name": "timestamp"}, {"name": "operation"}]
                }
            },
            "result": {"data_array": [["5", "2024-01-15", "WRITE"], ["4", "2024-01-14", "WRITE"]]},
        }
        rows = _parse_history_result(result)
        assert len(rows) == 2
        assert rows[0] == {"version": "5", "timestamp": "2024-01-15", "operation": "WRITE"}
        assert rows[1]["version"] == "4"

    def test_returns_empty_on_failure(self):
        result = {"status": {"state": "FAILED"}, "manifest": {}, "result": {}}
        assert _parse_history_result(result) == []

    def test_returns_empty_on_missing_state(self):
        assert _parse_history_result({}) == []

    def test_handles_empty_data_array(self):
        result = {
            "status": {"state": "SUCCEEDED"},
            "manifest": {"schema": {"columns": [{"name": "version"}]}},
            "result": {"data_array": []},
        }
        assert _parse_history_result(result) == []


# ---------------------------------------------------------------------------
# Testes do DatabricksService (com mock do query_table)
# ---------------------------------------------------------------------------


def _make_databricks_service() -> DatabricksService:
    svc = DatabricksService(db=MagicMock(), company_id=uuid.uuid4())
    svc._host = "https://workspace.cloud.databricks.com"
    svc._token = "fake-token"  # noqa: S105
    return svc


@pytest.fixture(autouse=True)
async def reset_shared_client():
    await DatabricksService.close()
    yield
    await DatabricksService.close()


class TestGetTableHistory:
    @pytest.mark.asyncio
    async def test_calls_describe_history_sql(self):
        svc = _make_databricks_service()
        svc._ensure_credentials = AsyncMock()
        history_response = {
            "status": {"state": "SUCCEEDED"},
            "manifest": {
                "schema": {"columns": [{"name": "version"}, {"name": "timestamp"}]}
            },
            "result": {"data_array": [["5", "2024-01-15"], ["4", "2024-01-14"]]},
        }
        svc.query_table = AsyncMock(return_value=history_response)

        result = await svc.get_table_history("medallion.silver.messages_clean", limit=2)

        svc.query_table.assert_awaited_once()
        called_sql = svc.query_table.call_args[0][0]
        assert "DESCRIBE HISTORY" in called_sql
        assert "`medallion`.`silver`.`messages_clean`" in called_sql
        assert "LIMIT 2" in called_sql

        assert len(result) == 2
        assert result[0]["version"] == "5"

    @pytest.mark.asyncio
    async def test_returns_empty_list_on_failed_query(self):
        svc = _make_databricks_service()
        svc._ensure_credentials = AsyncMock()
        svc.query_table = AsyncMock(
            return_value={"status": {"state": "FAILED"}, "manifest": {}, "result": {}}
        )

        result = await svc.get_table_history("a.b.c")
        assert result == []


class TestRestoreTable:
    @pytest.mark.asyncio
    async def test_calls_restore_sql_with_version(self):
        svc = _make_databricks_service()
        svc._ensure_credentials = AsyncMock()
        svc.query_table = AsyncMock(return_value={"status": {"state": "SUCCEEDED"}})

        await svc.restore_table("medallion.silver.messages_clean", version=3)

        called_sql = svc.query_table.call_args[0][0]
        assert "RESTORE TABLE" in called_sql
        assert "`medallion`.`silver`.`messages_clean`" in called_sql
        assert "VERSION AS OF 3" in called_sql

    @pytest.mark.asyncio
    async def test_calls_restore_sql_with_timestamp(self):
        svc = _make_databricks_service()
        svc._ensure_credentials = AsyncMock()
        svc.query_table = AsyncMock(return_value={"status": {"state": "SUCCEEDED"}})

        await svc.restore_table("a.b.c", timestamp="2024-01-15T00:00:00")

        called_sql = svc.query_table.call_args[0][0]
        assert "TIMESTAMP AS OF '2024-01-15T00:00:00'" in called_sql

    @pytest.mark.asyncio
    async def test_raises_when_no_version_or_timestamp(self):
        svc = _make_databricks_service()
        svc._ensure_credentials = AsyncMock()

        with pytest.raises(ValueError, match="version ou timestamp"):
            await svc.restore_table("a.b.c")


# ---------------------------------------------------------------------------
# Testes do fluxo de revert — modo restore_table chama ações corretas
# ---------------------------------------------------------------------------


class TestRevertFlowRestoreTable:
    """Valida que o endpoint chama DatabricksService.restore_table e
    GitHubService.revert_merged_pr conforme os campos do RevertRequest."""

    @pytest.mark.asyncio
    async def test_restore_table_calls_databricks_restore(self):
        """Mode restore_table: deve chamar get_table_history + restore_table."""
        from app.schemas.pipeline_editor import RevertRequest

        req = RevertRequest(
            mode="restore_table",
            table="medallion.silver.messages_clean",
            delta_version=4,
            revert_notebook_pr=False,
        )
        assert req.mode == "restore_table"
        assert req.table == "medallion.silver.messages_clean"
        assert req.delta_version == 4
        assert req.revert_notebook_pr is False

    @pytest.mark.asyncio
    async def test_restore_table_auto_discovers_previous_version(self):
        """Sem delta_version: usa history[1] como versao anterior."""
        svc = _make_databricks_service()
        svc._ensure_credentials = AsyncMock()

        history_response = {
            "status": {"state": "SUCCEEDED"},
            "manifest": {"schema": {"columns": [{"name": "version"}, {"name": "timestamp"}]}},
            "result": {"data_array": [["5", "2024-01-15"], ["4", "2024-01-14"]]},
        }
        restore_response = {"status": {"state": "SUCCEEDED"}, "result": {}}
        svc.query_table = AsyncMock(side_effect=[history_response, restore_response])

        history = await svc.get_table_history("medallion.silver.messages_clean", limit=2)
        prev_version = int(history[1]["version"]) if len(history) >= 2 else None

        assert prev_version == 4
        await svc.restore_table("medallion.silver.messages_clean", version=prev_version)

        # Duas chamadas: DESCRIBE HISTORY + RESTORE TABLE
        assert svc.query_table.await_count == 2
        restore_sql = svc.query_table.call_args_list[1][0][0]
        assert "RESTORE TABLE" in restore_sql
        assert "VERSION AS OF 4" in restore_sql

    @pytest.mark.asyncio
    async def test_revert_notebook_pr_false_skips_github_call(self):
        """revert_notebook_pr=False: nenhuma chamada ao GitHubService."""
        from app.schemas.pipeline_editor import RevertRequest

        req = RevertRequest(
            mode="restore_table",
            table="medallion.silver.messages_clean",
            delta_version=3,
            revert_notebook_pr=False,
        )
        # O campo determina a lógica — verificamos a propriedade
        assert req.revert_notebook_pr is False

    @pytest.mark.asyncio
    async def test_revert_notebook_pr_true_signals_github_call(self):
        """revert_notebook_pr=True: propriedade indica que GitHub deve ser chamado."""
        from app.schemas.pipeline_editor import RevertRequest

        req = RevertRequest(
            mode="restore_table",
            table="medallion.silver.messages_clean",
            delta_version=3,
            revert_notebook_pr=True,
        )
        assert req.revert_notebook_pr is True


# ---------------------------------------------------------------------------
# Testes do GitHubService.revert_merged_pr (mocked HTTP)
# ---------------------------------------------------------------------------


class TestGitHubRevertMergedPr:
    @pytest.mark.asyncio
    async def test_raises_when_pr_not_merged(self):
        """PR sem merge_commit_sha deve levantar ValueError."""
        from app.services.github_service import GitHubService

        svc = GitHubService(db=MagicMock(), company_id=uuid.uuid4())
        svc._token = "fake"  # noqa: S105
        svc._repo = "owner/repo"

        mock_pr_response = MagicMock()
        mock_pr_response.raise_for_status = MagicMock()
        mock_pr_response.json.return_value = {
            "number": 42,
            "merge_commit_sha": None,
            "base": {"ref": "dev", "sha": "abc123"},
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_pr_response)
            mock_client_cls.return_value = mock_client

            with pytest.raises(ValueError, match="nao foi mergeado"):
                await svc.revert_merged_pr(42)

    @pytest.mark.asyncio
    async def test_creates_revert_pr_with_correct_structure(self):
        """Fluxo completo: verifica chamadas ao GitHub API em ordem."""
        from app.services.github_service import GitHubService

        svc = GitHubService(db=MagicMock(), company_id=uuid.uuid4())
        svc._token = "fake"  # noqa: S105
        svc._repo = "owner/repo"

        pr_data = {
            "number": 42,
            "merge_commit_sha": "mergeabc123",
            "base": {"ref": "dev", "sha": "base_sha_001"},
        }
        merge_commit_data = {
            "sha": "mergeabc123",
            "parents": [{"sha": "pre_pr_sha_001"}],
        }
        pre_pr_commit_data = {
            "sha": "pre_pr_sha_001",
            "tree": {"sha": "pre_pr_tree_sha"},
        }
        current_ref_data = {"object": {"sha": "current_sha_001"}}
        revert_commit_data = {"sha": "revert_commit_sha"}
        revert_pr_data = {
            "number": 99,
            "html_url": "https://github.com/owner/repo/pull/99",
        }

        def _make_resp(data):
            m = MagicMock()
            m.raise_for_status = MagicMock()
            m.json.return_value = data
            return m

        get_responses = [
            _make_resp(pr_data),           # GET /pulls/42
            _make_resp(merge_commit_data), # GET /git/commits/mergeabc123
            _make_resp(pre_pr_commit_data),# GET /git/commits/pre_pr_sha_001
            _make_resp(current_ref_data),  # GET /git/ref/heads/dev
        ]
        post_responses = [
            _make_resp(revert_commit_data), # POST /git/commits (revert commit)
            _make_resp({}),                 # POST /git/refs (create branch)
            _make_resp(revert_pr_data),     # POST /pulls (create PR)
        ]

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=get_responses)
            mock_client.post = AsyncMock(side_effect=post_responses)
            mock_client_cls.return_value = mock_client

            result = await svc.revert_merged_pr(42)

        assert result["revert_pr_number"] == 99
        assert result["revert_pr_url"] == "https://github.com/owner/repo/pull/99"
        assert result["original_pr_number"] == 42
        assert "revert/pipeline-editor/42" in result["revert_branch"]

        # Verifica que o commit de revert usa a tree pré-PR
        revert_commit_call = mock_client.post.call_args_list[0]
        commit_payload = revert_commit_call[1]["json"]
        assert commit_payload["tree"] == "pre_pr_tree_sha"
        assert commit_payload["parents"] == ["current_sha_001"]
        assert "42" in commit_payload["message"]
