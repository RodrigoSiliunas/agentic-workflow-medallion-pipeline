"""Módulo de diagnóstico de erros via Claude API (Opus 4.6).

Analisa stack traces, código, schema e contexto do pipeline
para propor correções precisas com código completo.
"""

import json
import os
import re

import anthropic

# Modelo: Opus 4.6 para máxima capacidade de diagnóstico
MODEL = "claude-opus-4-20250514"
MAX_TOKENS = 16000


def get_client() -> anthropic.Anthropic:
    """Cria cliente Anthropic. Falha se chave não configurada."""
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def diagnose_error(
    error_message: str,
    stack_trace: str,
    failed_task: str,
    notebook_code: str,
    schema_info: str,
    pipeline_state: dict,
) -> dict:
    """Envia contexto completo do erro para Claude Opus e recebe
    diagnóstico estruturado + código corrigido.

    Args:
        error_message: Mensagem de erro principal
        stack_trace: Stack trace completo (pode ser diferente do error)
        failed_task: Nome da task que falhou (ex: bronze_ingestion)
        notebook_code: Código fonte completo do notebook
        schema_info: Schema detalhado das tabelas (DESCRIBE + colunas)
        pipeline_state: Dict com run_id, task_results, delta_versions, etc.

    Returns:
        Dict com: diagnosis, root_cause, fix_description, fixed_code,
                  file_to_fix, confidence, requires_human_review
    """
    client = get_client()

    system_prompt = (
        "Você é um engenheiro de dados senior especializado em "
        "PySpark, Delta Lake, Databricks e pipelines Medallion.\n\n"
        "Seu trabalho é diagnosticar erros em pipelines de dados "
        "e propor correções de código COMPLETAS e funcionais.\n\n"
        "Regras:\n"
        "- Responda SEMPRE em JSON válido\n"
        "- Seja específico e técnico sobre a causa raiz\n"
        "- O campo fixed_code deve conter o notebook COMPLETO "
        "corrigido (não apenas o trecho alterado)\n"
        "- O campo file_to_fix deve ser o path relativo ao repo "
        "(ex: pipeline/notebooks/bronze/ingest.py)\n"
        "- Indique confiança realista (0.0 a 1.0)\n"
        "- Se não tiver certeza, diga e sugira investigação\n"
        "- NUNCA invente informações sobre schema ou dados\n"
        "- Considere que o pipeline roda em Databricks serverless "
        "ou cluster AWS com acesso S3 via boto3"
    )

    user_prompt = f"""O pipeline Medallion falhou. Preciso de diagnóstico e correção.

## Task que falhou
{failed_task}

## Mensagem de erro
{error_message}

## Stack Trace
{stack_trace}

## Código fonte do notebook que falhou
```python
{notebook_code}
```

## Schema das tabelas no Unity Catalog
{schema_info}

## Estado completo do pipeline
```json
{json.dumps(pipeline_state, indent=2, default=str)}
```

## Responda em JSON com esta estrutura EXATA:
{{
    "diagnosis": "Descrição clara e técnica do que aconteceu",
    "root_cause": "Causa raiz técnica específica",
    "fix_description": "O que foi alterado no código e por que",
    "fixed_code": "Código COMPLETO do notebook corrigido",
    "file_to_fix": "pipeline/notebooks/path/to/file.py",
    "confidence": 0.0,
    "requires_human_review": true,
    "additional_notes": "Notas extras ou investigações sugeridas"
}}"""

    # Streaming obrigatório para Opus com max_tokens alto
    text = ""
    input_tokens = 0
    output_tokens = 0
    with client.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    ) as stream:
        for event_text in stream.text_stream:
            text += event_text
        # Coletar usage após stream finalizar
        response = stream.get_final_message()
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        # Tentar extrair JSON de dentro de markdown code block
        json_match = re.search(
            r"```(?:json)?\s*(.*?)```", text, re.DOTALL
        )
        if json_match:
            result = json.loads(json_match.group(1))
        else:
            result = {
                "diagnosis": text[:500],
                "root_cause": "Resposta não estruturada do LLM",
                "fix_description": text[:500],
                "fixed_code": None,
                "file_to_fix": None,
                "confidence": 0.3,
                "requires_human_review": True,
                "additional_notes": (
                    "Resposta do LLM não estava em JSON. "
                    "Raw response truncada incluída no diagnosis."
                ),
            }

    # Metadados da chamada para auditoria
    result["_model"] = MODEL
    result["_input_tokens"] = input_tokens
    result["_output_tokens"] = output_tokens

    return result
