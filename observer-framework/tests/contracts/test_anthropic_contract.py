"""Contract tests — forma de resposta da API Anthropic (T7 F5).

Fixa o shape esperado (atributos + tipos) dos eventos consumidos por
`AnthropicChatProvider` e `AnthropicProvider.diagnose()`. Mudança de
shape no SDK anthropic → estes testes quebram, sinalizando breaking
change antes do runtime em produção.

Hoje usa fakes estruturais (sem rede). Quando VCR estiver ativo, os
mesmos testes consumirão cassettes gravados.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from observer.chat import (
    ChatEndEvent,
    ChatTokenEvent,
    ChatToolUseEvent,
    ToolSpec,
    create_chat_provider,
)

# ---------------------------------------------------------------------------
# Fake anthropic SDK replicando os atributos que usamos
# ---------------------------------------------------------------------------


class _FakeDelta:
    type = "content_block_delta"

    def __init__(self, text: str):
        self.delta = SimpleNamespace(text=text)


class _FakeToolUseBlock:
    type = "tool_use"

    def __init__(self, id: str, name: str, input: dict):
        self.id = id
        self.name = name
        self.input = input


class _FakeStreamCtx:
    def __init__(self, deltas: list, final_blocks: list):
        self._deltas = deltas
        self._final_blocks = final_blocks

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    def __aiter__(self):
        return self._iter()

    async def _iter(self):
        for d in self._deltas:
            yield d

    async def get_final_message(self):
        return SimpleNamespace(
            content=self._final_blocks,
            usage=SimpleNamespace(input_tokens=10, output_tokens=20),
            stop_reason="end_turn",
        )


def _inject_fake_client(provider, deltas, final_blocks):
    from unittest.mock import MagicMock

    stream_ctx = _FakeStreamCtx(deltas, final_blocks)
    client = MagicMock()
    client.messages.stream = MagicMock(return_value=stream_ctx)
    provider._client = client


# ---------------------------------------------------------------------------
# Contract: chat single round
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_chat_single_round_contract():
    """Resposta sem tool_use termina em ChatEndEvent com tokens contados."""
    provider = create_chat_provider("anthropic", api_key="sk-fake")
    _inject_fake_client(
        provider,
        deltas=[_FakeDelta("Jobs: "), _FakeDelta("42")],
        final_blocks=[SimpleNamespace(type="text", text="Jobs: 42")],
    )

    events = [
        e
        async for e in provider.stream_with_tools(
            model="claude-sonnet-4-20250514",
            system="",
            messages=[{"role": "user", "content": "how many jobs?"}],
            tools=[],
        )
    ]
    tokens = [e for e in events if isinstance(e, ChatTokenEvent)]
    end = next(e for e in events if isinstance(e, ChatEndEvent))

    # Contract checks
    assert [t.text for t in tokens] == ["Jobs: ", "42"]
    assert end.output_tokens == 20
    assert end.input_tokens == 10
    assert end.stop_reason == "end_turn"


# ---------------------------------------------------------------------------
# Contract: chat com tool_use round
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_chat_tool_use_contract():
    """Tool use emerge como ChatToolUseEvent com id/name/input."""
    provider = create_chat_provider("anthropic", api_key="sk-fake")
    tool_block = _FakeToolUseBlock(
        id="toolu_01XYZ",
        name="list_databricks_jobs",
        input={"limit": 5},
    )
    _inject_fake_client(
        provider,
        deltas=[_FakeDelta("Let me list jobs.")],
        final_blocks=[tool_block],
    )

    events = [
        e
        async for e in provider.stream_with_tools(
            model="claude-sonnet-4-20250514",
            system="",
            messages=[{"role": "user", "content": "list jobs"}],
            tools=[
                ToolSpec(
                    name="list_databricks_jobs",
                    description="Lista jobs",
                    input_schema={"type": "object"},
                )
            ],
        )
    ]

    tool_uses = [e for e in events if isinstance(e, ChatToolUseEvent)]
    assert len(tool_uses) == 1
    assert tool_uses[0].id == "toolu_01XYZ"
    assert tool_uses[0].name == "list_databricks_jobs"
    assert tool_uses[0].input == {"limit": 5}


# ---------------------------------------------------------------------------
# Contract: Diagnosis (legacy LLMProvider) — smoke de shape
# ---------------------------------------------------------------------------


def test_diagnosis_result_shape_contract():
    """DiagnosisResult deve ter os campos que o workflow observer assume."""
    from observer.providers.base import DiagnosisResult

    result = DiagnosisResult(
        diagnosis="d",
        root_cause="r",
        fix_description="f",
        fixed_code="x",
        file_to_fix="foo.py",
        confidence=0.5,
    )

    # Campos obrigatórios
    assert hasattr(result, "normalized_fixes")
    assert hasattr(result, "to_dict")
    # Shape esperado pelo GitHubProvider
    d = result.to_dict()
    for field in (
        "diagnosis",
        "root_cause",
        "fix_description",
        "fixed_code",
        "file_to_fix",
        "fixes",
        "confidence",
        "requires_human_review",
        "additional_notes",
    ):
        assert field in d


def test_diagnosis_request_shape_contract():
    from observer.providers.base import DiagnosisRequest

    req = DiagnosisRequest(
        error_message="e",
        stack_trace="s",
        failed_task="t",
        notebook_code="c",
        schema_info="i",
    )

    assert hasattr(req, "error_message")
    assert hasattr(req, "stack_trace")
    assert hasattr(req, "failed_task")
    assert hasattr(req, "notebook_code")
    assert hasattr(req, "schema_info")
    assert hasattr(req, "pipeline_state")
