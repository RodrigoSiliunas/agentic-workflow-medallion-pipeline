"""Tools que consomem `DatabricksService` (T7 F4)."""

from __future__ import annotations

from typing import Any

from app.services.tools.base import ToolContext, register_tool

_FORBIDDEN_SQL_TOKENS = {
    "INSERT", "UPDATE", "DELETE", "DROP", "CREATE",
    "ALTER", "TRUNCATE", "EXEC", "GRANT", "REVOKE",
}


@register_tool("list_databricks_jobs")
class ListDatabricksJobs:
    name = "list_databricks_jobs"
    description = "Lista todos os jobs/workflows do Databricks com job_id e nome."
    input_schema = {
        "type": "object",
        "properties": {"limit": {"type": "integer", "default": 20}},
    }

    async def run(self, ctx: ToolContext, input_data: dict[str, Any]) -> dict[str, Any]:
        jobs = await ctx.databricks.list_jobs(input_data.get("limit", 20))
        return {"jobs": jobs}


@register_tool("get_job_details")
class GetJobDetails:
    name = "get_job_details"
    description = "Config completa de um job: schedule, tasks, timeout, tags."
    input_schema = {
        "type": "object",
        "properties": {"job_id": {"type": "integer"}},
        "required": ["job_id"],
    }

    async def run(self, ctx: ToolContext, input_data: dict[str, Any]) -> dict[str, Any]:
        return await ctx.databricks.get_job_details(input_data["job_id"])


@register_tool("update_job_schedule")
class UpdateJobSchedule:
    name = "update_job_schedule"
    description = (
        "Altera cron de um job. REQUER CONFIRMACAO. "
        "Quartz: '0 0 6 * * ?' = diario 6h."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "job_id": {"type": "integer"},
            "cron": {
                "type": "string",
                "description": "Quartz cron (ex: '0 0 6 * * ?')",
            },
            "timezone": {"type": "string", "default": "America/Sao_Paulo"},
            "paused": {"type": "boolean", "default": False},
        },
        "required": ["job_id", "cron"],
    }
    requires_confirmation = True

    async def run(self, ctx: ToolContext, input_data: dict[str, Any]) -> dict[str, Any]:
        return await ctx.databricks.update_job_schedule(
            job_id=input_data["job_id"],
            cron=input_data["cron"],
            timezone=input_data.get("timezone", "America/Sao_Paulo"),
            paused=input_data.get("paused", False),
        )


@register_tool("update_job_settings")
class UpdateJobSettings:
    name = "update_job_settings"
    description = "Atualiza config de um job (timeout, tags). REQUER CONFIRMACAO."
    input_schema = {
        "type": "object",
        "properties": {
            "job_id": {"type": "integer"},
            "settings": {
                "type": "object",
                "description": "Settings a alterar",
            },
        },
        "required": ["job_id", "settings"],
    }
    requires_confirmation = True

    async def run(self, ctx: ToolContext, input_data: dict[str, Any]) -> dict[str, Any]:
        return await ctx.databricks.update_job_settings(
            job_id=input_data["job_id"],
            settings=input_data["settings"],
        )


@register_tool("get_pipeline_status")
class GetPipelineStatus:
    name = "get_pipeline_status"
    description = "Retorna status atual do pipeline (running, idle, failed)."
    input_schema = {
        "type": "object",
        "properties": {"pipeline_job_id": {"type": "integer"}},
        "required": ["pipeline_job_id"],
    }

    async def run(self, ctx: ToolContext, input_data: dict[str, Any]) -> dict[str, Any]:
        return await ctx.databricks.get_pipeline_summary(input_data["pipeline_job_id"])


@register_tool("get_run_logs")
class GetRunLogs:
    name = "get_run_logs"
    description = "Busca logs de uma run especifica do pipeline."
    input_schema = {
        "type": "object",
        "properties": {"run_id": {"type": "integer"}},
        "required": ["run_id"],
    }

    async def run(self, ctx: ToolContext, input_data: dict[str, Any]) -> dict[str, Any]:
        return await ctx.databricks.get_run_output(input_data["run_id"])


@register_tool("query_delta_table")
class QueryDeltaTable:
    name = "query_delta_table"
    description = "Executa SELECT SQL em tabelas Delta. Apenas SELECT."
    input_schema = {
        "type": "object",
        "properties": {
            "sql": {"type": "string", "description": "Query SQL (SELECT only)"},
            "max_rows": {"type": "integer", "default": 50},
        },
        "required": ["sql"],
    }

    async def run(self, ctx: ToolContext, input_data: dict[str, Any]) -> dict[str, Any]:
        sql = input_data["sql"].strip()
        sql_upper = sql.upper()
        if not sql_upper.startswith("SELECT"):
            return {"error": "Apenas queries SELECT sao permitidas"}
        if ";" in sql:
            return {"error": "Multi-statement nao permitido"}
        tokens = set(sql_upper.split())
        forbidden = tokens & _FORBIDDEN_SQL_TOKENS
        if forbidden:
            return {"error": f"Palavras proibidas detectadas: {forbidden}"}
        return await ctx.databricks.query_table(sql, input_data.get("max_rows", 50))


@register_tool("get_table_schema")
class GetTableSchema:
    name = "get_table_schema"
    description = "Retorna schema completo de uma tabela Delta."
    input_schema = {
        "type": "object",
        "properties": {"catalog": {"type": "string", "default": "medallion"}},
    }

    async def run(self, ctx: ToolContext, input_data: dict[str, Any]) -> dict[str, Any]:
        schemas = await ctx.databricks.get_table_schemas(input_data.get("catalog", "medallion"))
        return {"schemas": schemas}
