"""Testes do TOOL_REGISTRY backend (T7 F4)."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from app.services.tools import (
    TOOL_REGISTRY,
    all_tool_specs,
    confirmation_required_tools,
    register_tool,
)
from app.services.tools.databricks_tools import QueryDeltaTable


class TestRegistryPopulation:
    def test_core_tools_registered(self):
        expected = {
            "list_databricks_jobs",
            "get_job_details",
            "update_job_schedule",
            "update_job_settings",
            "get_pipeline_status",
            "get_run_logs",
            "query_delta_table",
            "get_table_schema",
            "read_file",
            "list_recent_prs",
            "get_pr_diff",
            "create_pull_request",
            "trigger_pipeline_run",
        }
        assert expected.issubset(set(TOOL_REGISTRY.keys()))

    def test_each_entry_is_class(self):
        for cls in TOOL_REGISTRY.values():
            assert isinstance(cls, type)


class TestAllToolSpecs:
    def test_returns_tool_spec_objects(self):
        specs = all_tool_specs()
        assert len(specs) == len(TOOL_REGISTRY)
        for spec in specs:
            assert hasattr(spec, "name")
            assert hasattr(spec, "description")
            assert hasattr(spec, "input_schema")

    def test_spec_names_match_registry(self):
        specs = all_tool_specs()
        assert {s.name for s in specs} == set(TOOL_REGISTRY.keys())


class TestConfirmationFlags:
    def test_destructive_tools_require_confirmation(self):
        required = confirmation_required_tools()
        expected = {
            "update_job_schedule",
            "update_job_settings",
            "create_pull_request",
            "trigger_pipeline_run",
        }
        assert expected.issubset(required)

    def test_read_only_tools_dont_require_confirmation(self):
        required = confirmation_required_tools()
        read_only_tools = (
            "list_databricks_jobs",
            "get_job_details",
            "query_delta_table",
            "read_file",
        )
        for read_only in read_only_tools:
            assert read_only not in required


class TestRegisterDecorator:
    def test_decorator_adds_entry(self):
        @register_tool("__test-tool__")
        class _TestTool:
            name = "__test-tool__"
            description = "x"
            input_schema: dict = {"type": "object"}

            async def run(self, ctx, input_data):  # noqa: ANN001
                return {"ok": True}

        try:
            assert TOOL_REGISTRY["__test-tool__"] is _TestTool
        finally:
            TOOL_REGISTRY.pop("__test-tool__", None)

    def test_decorator_sets_name_if_missing(self):
        @register_tool("__no-name-tool__")
        class _NoName:
            description = "y"
            input_schema: dict = {"type": "object"}

            async def run(self, ctx, input_data):  # noqa: ANN001
                return {}

        try:
            assert _NoName.name == "__no-name-tool__"  # type: ignore[attr-defined]
        finally:
            TOOL_REGISTRY.pop("__no-name-tool__", None)

    def test_decorator_defaults_requires_confirmation_false(self):
        @register_tool("__default-conf__")
        class _NoConf:
            description = "y"
            input_schema: dict = {"type": "object"}

            async def run(self, ctx, input_data):  # noqa: ANN001
                return {}

        try:
            assert _NoConf.requires_confirmation is False  # type: ignore[attr-defined]
        finally:
            TOOL_REGISTRY.pop("__default-conf__", None)


def _run_query_guard(sql: str) -> dict:
    async def _run():
        return await QueryDeltaTable().run(MagicMock(), {"sql": sql})

    return asyncio.run(_run())


class TestQueryDeltaTableGuards:
    def test_rejects_non_select(self):
        result = _run_query_guard("DROP TABLE x")
        assert "error" in result

    def test_rejects_multi_statement(self):
        result = _run_query_guard("SELECT 1; SELECT 2")
        assert "error" in result
        assert "Multi-statement" in result["error"]

    def test_rejects_forbidden_standalone_keyword(self):
        # Guard whitespace-split pega tokens standalone
        result = _run_query_guard("SELECT * FROM x WHERE DELETE IS NULL")
        assert "error" in result
        assert "Palavras proibidas" in result["error"]
