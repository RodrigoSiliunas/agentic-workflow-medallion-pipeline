"""Provider LLM: Anthropic (Claude Opus, Sonnet, Haiku)."""

from __future__ import annotations

import json
import re

import anthropic

from pipeline_lib.agent.observer.providers import register_llm_provider
from pipeline_lib.agent.observer.providers.base import (
    DiagnosisRequest,
    DiagnosisResult,
    LLMProvider,
)

SYSTEM_PROMPT = (
    "Voce e um engenheiro de dados senior especializado em "
    "PySpark, Delta Lake, Databricks e pipelines Medallion.\n\n"
    "Seu trabalho e diagnosticar erros em pipelines de dados "
    "e propor correcoes de codigo COMPLETAS e funcionais.\n\n"
    "Regras:\n"
    "- Responda SEMPRE em JSON valido\n"
    "- Seja especifico e tecnico sobre a causa raiz\n"
    "- O campo fixed_code deve conter o notebook COMPLETO "
    "corrigido (nao apenas o trecho alterado)\n"
    "- O campo file_to_fix deve ser o path relativo ao repo "
    "(ex: pipeline/notebooks/bronze/ingest.py)\n"
    "- Indique confianca realista (0.0 a 1.0)\n"
    "- Se nao tiver certeza, diga e sugira investigacao\n"
    "- NUNCA invente informacoes sobre schema ou dados"
)


@register_llm_provider("anthropic")
class AnthropicProvider(LLMProvider):
    """Claude API via Anthropic SDK (streaming)."""

    def __init__(
        self,
        api_key: str = "",
        model: str = "claude-opus-4-20250514",
        max_tokens: int = 16000,
    ):
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens

    @property
    def name(self) -> str:
        return "anthropic"

    def diagnose(self, request: DiagnosisRequest) -> DiagnosisResult:
        client = anthropic.Anthropic(api_key=self._api_key)

        user_prompt = self._build_prompt(request)

        # Streaming obrigatorio para Opus com max_tokens alto
        text = ""
        input_tokens = 0
        output_tokens = 0

        with client.messages.stream(
            model=self._model,
            max_tokens=self._max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        ) as stream:
            for chunk in stream.text_stream:
                text += chunk
            response = stream.get_final_message()
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens

        # Parse JSON da resposta
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
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    def _build_prompt(self, req: DiagnosisRequest) -> str:
        return f"""O pipeline falhou. Preciso de diagnostico e correcao.

## Task que falhou
{req.failed_task}

## Mensagem de erro
{req.error_message}

## Stack Trace
{req.stack_trace}

## Codigo fonte do notebook
```python
{req.notebook_code}
```

## Schema das tabelas
{req.schema_info}

## Estado do pipeline
```json
{json.dumps(req.pipeline_state, indent=2, default=str)}
```

## Responda em JSON:
{{
    "diagnosis": "...",
    "root_cause": "...",
    "fix_description": "...",
    "fixed_code": "codigo completo corrigido",
    "file_to_fix": "pipeline/notebooks/...",
    "confidence": 0.0,
    "requires_human_review": true,
    "additional_notes": "..."
}}"""

    def _parse_json(self, text: str) -> dict:
        """Extrai JSON da resposta, com fallback para code blocks."""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            return {
                "diagnosis": text[:500],
                "root_cause": "Resposta nao estruturada",
                "confidence": 0.3,
                "requires_human_review": True,
            }
