"""Provider LLM: Anthropic (Claude Opus, Sonnet, Haiku)."""

from __future__ import annotations

import json
import re

import anthropic

from observer.providers import register_llm_provider
from observer.providers.base import (
    DiagnosisRequest,
    DiagnosisResult,
    LLMProvider,
    with_retry,
)

SYSTEM_PROMPT = (
    "Você é um engenheiro de dados senior especializado em "
    "PySpark, Delta Lake, Databricks e pipelines Medallion.\n\n"
    "Seu trabalho é diagnosticar erros em pipelines de dados "
    "e propor correções de código COMPLETAS e funcionais.\n\n"
    "Regras:\n"
    "- Responda SEMPRE em JSON válido\n"
    "- Seja específico e técnico sobre a causa raiz\n"
    "- Cada arquivo retornado deve conter o CONTEÚDO COMPLETO "
    "corrigido (não apenas o trecho alterado)\n"
    "- Paths são sempre relativos ao repo (ex: pipeline/notebooks/bronze/ingest.py)\n"
    "- Indique confiança realista (0.0 a 1.0)\n"
    "- Se não tiver certeza, diga e sugira investigação\n"
    "- NUNCA invente informações sobre schema ou dados\n\n"
    "Formato da resposta:\n"
    "- Para fix em UM arquivo: use os campos `fixed_code` + `file_to_fix`\n"
    "- Para fix em MÚLTIPLOS arquivos (bugs cruzando módulos): use o campo "
    "`fixes` com uma lista de `{\"file_path\": \"...\", \"code\": \"...\"}`. "
    "Quando usar `fixes`, NÃO preencha `fixed_code`/`file_to_fix`.\n"
    "- Prefira multi-file apenas quando o bug REALMENTE exige mudanças em "
    "arquivos diferentes (ex: schema contract + notebook que usa o schema)"
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

    @with_retry(max_retries=3, base_delay=2.0)
    def diagnose(self, request: DiagnosisRequest) -> DiagnosisResult:
        client = anthropic.Anthropic(api_key=self._api_key)

        user_prompt = self._build_prompt(request)

        # Streaming obrigatório para Opus com max_tokens alto
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
            fixes=data.get("fixes"),
            confidence=float(data.get("confidence", 0.0)),
            requires_human_review=data.get("requires_human_review", True),
            additional_notes=data.get("additional_notes", ""),
            provider=self.name,
            model=self._model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    def _build_prompt(self, req: DiagnosisRequest) -> str:
        return f"""O pipeline falhou. Preciso de diagnóstico e correção.

## Task que falhou
{req.failed_task}

## Mensagem de erro
{req.error_message}

## Stack Trace
{req.stack_trace}

## Código fonte do notebook
```python
{req.notebook_code}
```

## Schema das tabelas
{req.schema_info}

## Estado do pipeline
```json
{json.dumps(req.pipeline_state, indent=2, default=str)}
```

## Responda em JSON.

Para fix em UM arquivo (caso comum):
{{
    "diagnosis": "...",
    "root_cause": "...",
    "fix_description": "...",
    "fixed_code": "código completo corrigido do arquivo",
    "file_to_fix": "pipeline/notebooks/...",
    "confidence": 0.0,
    "requires_human_review": true,
    "additional_notes": "..."
}}

Para fix em MÚLTIPLOS arquivos (quando o bug cruza módulos):
{{
    "diagnosis": "...",
    "root_cause": "...",
    "fix_description": "...",
    "fixes": [
        {{"file_path": "pipeline/.../a.py", "code": "arquivo A completo"}},
        {{"file_path": "pipeline/.../b.py", "code": "arquivo B completo"}}
    ],
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
                "root_cause": "Resposta não estruturada",
                "confidence": 0.3,
                "requires_human_review": True,
            }
