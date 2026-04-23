"""Teste do LLMOrchestrator refatorado para observer.chat (T7 F3)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from observer.chat import ChatEndEvent, ChatErrorEvent, ChatTokenEvent, ChatToolUseEvent

from app.services.llm_orchestrator import LLMOrchestrator


def _make_orchestrator() -> LLMOrchestrator:
    db = MagicMock()
    return LLMOrchestrator(
        db=db,
        company_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        user_name="tester",
    )


class _FakeContext:
    def __init__(self):
        self.system_prompt = "you are helpful"
        self.blocks: list = []


async def _collect_events(gen) -> list[dict]:
    return [e async for e in gen]


@pytest.mark.anyio
async def test_single_round_no_tool_yields_token_then_done():
    orch = _make_orchestrator()
    orch._get_model = AsyncMock(return_value="claude-sonnet-4-20250514")
    orch.context_engine.assemble = AsyncMock(return_value=_FakeContext())

    mock_provider = MagicMock()

    async def fake_stream(**kwargs):
        yield ChatTokenEvent(text="Hello")
        yield ChatTokenEvent(text=" there")
        yield ChatEndEvent(content_blocks=[], output_tokens=15)

    mock_provider.stream_with_tools = fake_stream
    orch._get_chat_provider = AsyncMock(return_value=(mock_provider, "anthropic"))

    events = await _collect_events(orch.process_message(
        user_message="hi",
        pipeline_job_id=1,
        conversation_history=[],
    ))

    types = [e["type"] for e in events]
    assert types == ["token", "token", "done"]
    assert events[0]["content"] == "Hello"
    assert events[-1]["tokens"] == 15


@pytest.mark.anyio
async def test_tool_use_round_executes_tool_then_finalizes():
    orch = _make_orchestrator()
    orch._get_model = AsyncMock(return_value="model")
    orch.context_engine.assemble = AsyncMock(return_value=_FakeContext())

    orch._execute_tool = AsyncMock(return_value={"jobs": [{"job_id": 42}]})

    round_counter = {"n": 0}

    async def fake_stream(**kwargs):
        round_counter["n"] += 1
        if round_counter["n"] == 1:
            yield ChatToolUseEvent(id="tu1", name="list_databricks_jobs", input={"limit": 5})
            yield ChatEndEvent(content_blocks=[], output_tokens=5)
        else:
            yield ChatTokenEvent(text="Done.")
            yield ChatEndEvent(content_blocks=[], output_tokens=3)

    mock_provider = MagicMock()
    mock_provider.stream_with_tools = fake_stream
    orch._get_chat_provider = AsyncMock(return_value=(mock_provider, "anthropic"))

    events = await _collect_events(orch.process_message(
        user_message="list jobs",
        pipeline_job_id=1,
        conversation_history=[],
    ))

    types = [e["type"] for e in events]
    # Round 1: action; Round 2: token + done
    assert "action" in types
    assert "done" in types

    action_event = next(e for e in events if e["type"] == "action")
    assert action_event["action"] == "list_databricks_jobs"
    assert action_event["status"] == "success"
    orch._execute_tool.assert_awaited_once_with("list_databricks_jobs", {"limit": 5})


@pytest.mark.anyio
async def test_chat_error_propagates_as_sse_error():
    orch = _make_orchestrator()
    orch._get_model = AsyncMock(return_value="m")
    orch.context_engine.assemble = AsyncMock(return_value=_FakeContext())

    async def fake_stream(**kwargs):
        yield ChatErrorEvent(message="network down", exception_type="TimeoutError")

    mock_provider = MagicMock()
    mock_provider.stream_with_tools = fake_stream
    orch._get_chat_provider = AsyncMock(return_value=(mock_provider, "anthropic"))

    events = await _collect_events(orch.process_message(
        user_message="x",
        pipeline_job_id=1,
        conversation_history=[],
    ))

    assert len(events) == 1
    assert events[0]["type"] == "error"
    assert events[0]["content"] == "network down"


@pytest.mark.anyio
async def test_max_rounds_reached_emits_error():
    orch = _make_orchestrator()
    orch._get_model = AsyncMock(return_value="m")
    orch.context_engine.assemble = AsyncMock(return_value=_FakeContext())
    orch._execute_tool = AsyncMock(return_value={"ok": True})

    # Sempre retorna tool_use — nunca encerra
    async def fake_stream(**kwargs):
        yield ChatToolUseEvent(id="loop", name="list_databricks_jobs", input={})
        yield ChatEndEvent(content_blocks=[], output_tokens=1)

    mock_provider = MagicMock()
    mock_provider.stream_with_tools = fake_stream
    orch._get_chat_provider = AsyncMock(return_value=(mock_provider, "anthropic"))

    events = await _collect_events(orch.process_message(
        user_message="x",
        pipeline_job_id=1,
        conversation_history=[],
    ))

    terminal = events[-1]
    assert terminal["type"] == "error"
    assert "rounds" in terminal["content"].lower()


class TestExecuteTool:
    @pytest.mark.anyio
    async def test_unknown_tool_returns_error(self):
        orch = _make_orchestrator()
        result = await orch._execute_tool("non_existent", {})
        assert "error" in result
        assert "desconhecida" in result["error"]

    @pytest.mark.anyio
    async def test_dispatches_via_registry(self):
        orch = _make_orchestrator()
        with patch(
            "app.services.tools.databricks_tools.ListDatabricksJobs.run",
            new_callable=AsyncMock,
            return_value={"jobs": [{"id": 1}]},
        ) as mock_run:
            result = await orch._execute_tool("list_databricks_jobs", {"limit": 5})
            assert result == {"jobs": [{"id": 1}]}
            mock_run.assert_awaited_once()

    @pytest.mark.anyio
    async def test_tool_exception_becomes_error_dict(self):
        orch = _make_orchestrator()
        with patch(
            "app.services.tools.databricks_tools.GetJobDetails.run",
            new_callable=AsyncMock,
            side_effect=RuntimeError("api down"),
        ):
            result = await orch._execute_tool("get_job_details", {"job_id": 1})
            assert result == {"error": "api down"}


class TestBackwardCompat:
    def test_tools_list_populated_from_registry(self):
        from app.services.llm_orchestrator import TOOLS

        names = {t["name"] for t in TOOLS}
        assert "list_databricks_jobs" in names
        assert "create_pull_request" in names

    def test_confirmation_required_set_populated(self):
        from app.services.llm_orchestrator import CONFIRMATION_REQUIRED

        assert "update_job_schedule" in CONFIRMATION_REQUIRED
        assert "create_pull_request" in CONFIRMATION_REQUIRED
        assert "list_databricks_jobs" not in CONFIRMATION_REQUIRED


def test_no_direct_anthropic_import():
    """Regressão de T7 F3 — backend.services não importa anthropic."""
    import pathlib

    services_dir = pathlib.Path(__file__).resolve().parents[2] / "app" / "services"
    offenders = []
    for py_file in services_dir.rglob("*.py"):
        source = py_file.read_text(encoding="utf-8")
        if "import anthropic" in source or "from anthropic" in source:
            offenders.append(str(py_file.relative_to(services_dir)))
    assert offenders == [], (
        f"app/services/ não deve importar anthropic diretamente. "
        f"Offenders: {offenders}"
    )
