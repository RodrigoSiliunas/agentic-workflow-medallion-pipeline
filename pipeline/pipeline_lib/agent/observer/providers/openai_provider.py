"""Provider LLM: OpenAI (GPT-4o, GPT-4, o1, etc).

Compatível com qualquer API OpenAI-compatible (Azure, Together, etc).
"""

from __future__ import annotations

import json
import re

from pipeline_lib.agent.observer.providers import register_llm_provider
from pipeline_lib.agent.observer.providers.anthropic_provider import (
    SYSTEM_PROMPT,
)
from pipeline_lib.agent.observer.providers.base import (
    DiagnosisRequest,
    DiagnosisResult,
    LLMProvider,
    with_retry,
)


@register_llm_provider("openai")
class OpenAIProvider(LLMProvider):
    """OpenAI API (GPT-4o, GPT-4, etc). Compatível com Azure OpenAI."""

    def __init__(
        self,
        api_key: str = "",
        model: str = "gpt-4o",
        max_tokens: int = 16000,
        base_url: str | None = None,
    ):
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens
        self._base_url = base_url

    @property
    def name(self) -> str:
        return "openai"

    @with_retry(max_retries=3, base_delay=2.0)
    def diagnose(self, request: DiagnosisRequest) -> DiagnosisResult:
        try:
            # Lazy import: optional dependency
            from openai import OpenAI
        except ImportError as e:
            raise ImportError(
                "openai package não instalado. "
                "Instale com: pip install openai"
            ) from e

        client = OpenAI(api_key=self._api_key, base_url=self._base_url)

        user_prompt = self._build_prompt(request)

        response = client.chat.completions.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )

        text = response.choices[0].message.content or ""
        usage = response.usage
        in_tok = usage.prompt_tokens if usage else 0
        out_tok = usage.completion_tokens if usage else 0

        data = self._parse_json(text)

        return DiagnosisResult(
            diagnosis=data.get("diagnosis", ""),
            root_cause=data.get("root_cause", ""),
            fix_description=data.get("fix_description", ""),
            fixed_code=data.get("fixed_code"),
            file_to_fix=data.get("file_to_fix"),
            confidence=float(data.get("confidence", 0.0)),
            requires_human_review=data.get("requires_human_review", True),
            additional_notes=data.get("additional_notes", ""),
            provider=self.name,
            model=self._model,
            input_tokens=in_tok,
            output_tokens=out_tok,
        )

    def _build_prompt(self, req: DiagnosisRequest) -> str:
        return f"""O pipeline falhou. Diagnóstico e correção necessários.

Task: {req.failed_task}
Erro: {req.error_message}
Stack: {req.stack_trace}

Código:
```python
{req.notebook_code}
```

Schema: {req.schema_info}
Estado: {json.dumps(req.pipeline_state, indent=2, default=str)}

Responda em JSON com: diagnosis, root_cause, fix_description,
fixed_code, file_to_fix, confidence, requires_human_review,
additional_notes."""

    def _parse_json(self, text: str) -> dict:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            return {
                "diagnosis": text[:500],
                "confidence": 0.3,
                "requires_human_review": True,
            }
