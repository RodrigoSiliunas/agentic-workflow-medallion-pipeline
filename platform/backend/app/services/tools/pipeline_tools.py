"""Tools que disparam runs do pipeline (T7 F4)."""

from __future__ import annotations

from typing import Any

from app.services.tools.base import ToolContext, register_tool


@register_tool("trigger_pipeline_run")
class TriggerPipelineRun:
    name = "trigger_pipeline_run"
    description = "Dispara execucao do pipeline. REQUER CONFIRMACAO."
    input_schema = {
        "type": "object",
        "properties": {"pipeline_job_id": {"type": "integer"}},
        "required": ["pipeline_job_id"],
    }
    requires_confirmation = True

    async def run(self, ctx: ToolContext, input_data: dict[str, Any]) -> dict[str, Any]:
        return await ctx.databricks.trigger_run(input_data["pipeline_job_id"])
